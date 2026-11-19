"""Read-only, offline Markdown link inventory. Python 3.10+, standard library."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
from urllib.parse import unquote


def key(text):
    return unicodedata.normalize('NFC', text).casefold()


def visible(text):
    """Ignore fenced/inline code and HTML comments; not a full Markdown parser."""
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    lines, fence = [], None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            marker = match[1]
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return re.sub(r'`+[^`\n]*`+', '', '\n'.join(lines))


def analyze(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Input must be a directory')
    notes, payloads = {}, {}
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if any(part.startswith('.') for part in rel.parts) or path.suffix.lower() != '.md':
            continue
        # Never read symlinks, including files beneath symlinked directories.
        if any((root / Path(*rel.parts[:n])).is_symlink() for n in range(1, len(rel.parts)+1)):
            continue
        if not path.is_file():
            continue
        data = path.read_bytes()
        name = rel.as_posix()
        payloads[name] = data.decode('utf-8-sig')
        notes[name] = {'id': name, 'sha256': hashlib.sha256(data).hexdigest()}
    exact, stems = defaultdict(list), defaultdict(list)
    for name in notes:
        exact[key(name)].append(name)
        stems[key(PurePosixPath(name).stem)].append(name)
    edges, unresolved = set(), []
    for source, text in payloads.items():
        text = visible(text)
        links = [(m.group(1).split('|')[0], True) for m in re.finditer(r'(?<!!)\[\[([^\]\n]+)\]\]', text)]
        # Angle-bracket destinations can contain spaces and parentheses.
        markdown_link = r'(?<!!)\[[^\]\n]*\]\((?:<([^<>\n]+)>|([^<>\s)]+))\)'
        links += [(m.group(1) or m.group(2), False) for m in re.finditer(markdown_link, text)]
        for raw, wiki in links:
            target = unquote(raw.split('#')[0]).strip('<> ')
            if not target or re.match(r'^[a-zA-Z][\w+.-]*:', target):
                continue
            if target.startswith(('/', '\\')) or '\\' in target:
                unresolved.append({'source': source, 'target': raw, 'reason': 'unsafe-path'})
                continue
            if not wiki and PurePosixPath(target).suffix.lower() != '.md':
                continue
            if not PurePosixPath(target).suffix:
                target += '.md'
            joined = PurePosixPath(source).parent / target
            normalized = []
            for part in joined.parts:
                if part == '..':
                    if not normalized:
                        normalized = None
                        break
                    normalized.pop()
                elif part != '.':
                    normalized.append(part)
            if normalized is None:
                candidates = []
                reason = 'unsafe-path'
            else:
                candidates = exact.get(key('/'.join(normalized)), [])
                if wiki and not candidates:
                    candidates = exact.get(key(target), [])
                    if not candidates and '/' not in target:
                        candidates = stems.get(key(PurePosixPath(target).stem), [])
                reason = 'ambiguous' if len(candidates) > 1 else 'missing'
            if len(candidates) == 1:
                edges.add((source, candidates[0]))
            else:
                unresolved.append({'source': source, 'target': raw, 'reason': reason})
    degree = {name: 0 for name in notes}
    graph = {name: set() for name in notes}
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
        graph[a].add(b)
        graph[b].add(a)
    components, seen = [], set()
    for start in sorted(notes):
        if start in seen:
            continue
        pending, group = [start], []
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            group.append(node)
            pending.extend(sorted(graph[node] - seen, reverse=True))
        components.append(sorted(group))
    hashes = defaultdict(list)
    for note in notes.values():
        hashes[note['sha256']].append(note['id'])
    return {'schema_version': 1, 'notes': list(notes.values()),
            'links': [{'source': a, 'target': b} for a, b in sorted(edges)],
            'unresolved': sorted(unresolved, key=lambda x: (x['source'], x['target'], x['reason'])),
            'isolated': sorted(n for n, d in degree.items() if not d),
            'components': components,
            'exact_duplicates': sorted(sorted(v) for v in hashes.values() if len(v) > 1)}


def preview_removal(report, excluded):
    """Simulate removing exact note IDs from the existing graph; never change files.

    Graph-only projection: remaining links are NOT re-resolved, so previously
    ambiguous links do not become resolved after a hypothetical removal.
    """
    excluded = set(excluded)
    original = {note['id'] for note in report['notes']}
    unknown = excluded - original
    if unknown:
        raise ValueError('Unknown exact note ID(s): ' + ', '.join(sorted(unknown)))
    remaining = original - excluded
    graph = {name: set() for name in remaining}
    affected = []
    for edge in report['links']:
        a, b = edge['source'], edge['target']
        if a in remaining and b in remaining:
            graph[a].add(b)
            graph[b].add(a)
        elif a in remaining and b in excluded:
            affected.append(dict(edge))
    components, seen = [], set()
    for start in sorted(remaining):
        if start in seen:
            continue
        stack, group = [start], []
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            group.append(node)
            stack.extend(sorted(graph[node] - seen, reverse=True))
        components.append(sorted(group))
    component_index = {name: i for i, group in enumerate(components) for name in group}
    split_groups = []
    for group in report['components']:
        indices = sorted({component_index[name] for name in group if name in remaining})
        if len(indices) > 1:
            split_groups.append({'original': list(group),
                                 'fragments': [components[i] for i in indices]})
    isolated = sorted(name for name, neighbors in graph.items() if not neighbors)
    return {'mode': 'graph-only-removal-preview', 'removed': sorted(excluded),
            'remaining_note_count': len(remaining), 'components': components,
            'split_groups': split_groups,
            'newly_isolated': sorted(set(isolated) - set(report['isolated'])),
            'dangling_resolved_links': sorted(affected, key=lambda x: (x['source'], x['target'])),
            'source_files_modified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vault', type=Path)
    parser.add_argument('--without', action='append', default=[], metavar='EXACT_NOTE_ID',
                        help='Preview graph removal only; repeat to simulate a batch. No files change.')
    args = parser.parse_args(argv)
    try:
        report = analyze(args.vault)
        if args.without:
            report['removal_preview'] = preview_removal(report, args.without)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(2, f'Cannot analyze vault: {exc}\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

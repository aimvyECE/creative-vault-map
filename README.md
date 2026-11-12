# Creative Vault Map

A small, offline, read-only map of a Markdown creative notebook. Find disconnected drafts, broken links and byte-identical notes before deciding what to organize. Built for writing, poetry and music notebooks, including a deliberately limited subset of Obsidian links.

**Status: early prototype.** AI-assisted implementation, no production deployments or user adoption claimed. Python 3.10+, standard library only. No accounts, telemetry, network calls, embeddings, or deletion/rewriting of source notes.

## Try the synthetic example

```sh
python vaultmap.py examples/vault > /tmp/vault-report.json
python -m unittest discover -s tests -v
```

For your own local notebook:

```sh
python vaultmap.py '/path/to/vault' > '/private/output/report.json'
```

Keep the output outside the source vault and in a private directory. The tool reads every visible UTF-8 `.md` file recursively. A decoding or I/O error stops the run rather than silently returning a partial inventory.

## What the report means

- `links`: deduplicated directed edges from ordinary `[text](relative.md)` links and `[[wiki links|aliases]]`; heading fragments are ignored.
- `unresolved`: missing notes, ambiguous basenames or unsafe paths. These are review candidates, not automatically proven broken links.
- `isolated`: notes without recognized incoming or outgoing links. An isolated poem can be perfectly intentional.
- `components`: groups connected in either direction. These are structural groups, **not semantic or artistic classifications**.
- `exact_duplicates`: byte-identical files, identified with SHA-256. Never delete solely because two copies match.

A creative workflow: inspect isolated drafts, connect related lyrics and poems intentionally, resolve ambiguous titles, then review duplicates manually. The tool makes no changes and never merges notes.

## Privacy and safety

The report omits note bodies, but **filenames, link targets, hashes and notebook structure can still be sensitive**. It is not anonymized. Do not commit real reports or vaults to GitHub. Only synthetic material belongs in this repository.

Hidden paths and symlinks are excluded. Link destinations are resolved only against the scanned inventory; the tool never opens a link target separately. No `..` escape above the vault root is resolved. Use a stable local copy during analysis: this is not a hardened sandbox for hostile files or concurrent filesystem changes.

## Scope and limitations

This is not a full Markdown parser or an Obsidian plugin. Fenced/inline code and HTML comments are ignored with simple parsing. Reference-style links, complex nested parentheses, multiline link labels, YAML frontmatter semantics, canvas files, assets and embeds are not modeled. Obsidian aliases declared in frontmatter are not indexed. Matching uses Unicode NFC and case-folding for portability; collisions are reported as ambiguous rather than guessed. Wiki links prefer a file in the source directory, then a vault-root path, then a unique basename. Markdown links resolve relative to the source note.

Performance is intentionally simple: all Markdown text is read into memory and the graph is built in memory. Start with a modest notebook. No full-text search, semantic similarity, automatic tagging or generative writing is claimed.

## Development

Tests cover missing and ambiguous links, relative URL decoding, aliases and headings, duplicates, components, ignored code, hidden files, symlinks, UTF-8 failure, stable output and body exclusion. CI runs the suite on Python 3.10 and 3.12.

Useful next contributions: a standards-compliant Markdown parser with fixtures; opt-in anonymized node IDs; streaming inventory for large vaults. Keep any fixtures synthetic. See [CONTRIBUTING.md](CONTRIBUTING.md).

MIT license. No third-party runtime dependencies.

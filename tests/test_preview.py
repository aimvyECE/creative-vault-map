import copy
import tempfile
from pathlib import Path
import unittest
from vaultmap import analyze, preview_removal


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name, body in {'verse.md': '[[index]]', 'index.md': '[[chorus]]',
                           'chorus.md': 'Song', 'private.md': 'Unlinked'}.items():
            (self.root / name).write_text(body)
        self.report = analyze(self.root)

    def test_bridge_removal(self):
        result = preview_removal(self.report, ['index.md'])
        self.assertEqual(result['newly_isolated'], ['chorus.md', 'verse.md'])
        self.assertEqual(result['split_groups'][0]['fragments'], [['chorus.md'], ['verse.md']])
        self.assertEqual(result['dangling_resolved_links'], [{'source': 'verse.md', 'target': 'index.md'}])

    def test_no_mutations(self):
        before = copy.deepcopy(self.report)
        files = {p.name: p.read_bytes() for p in self.root.iterdir()}
        preview_removal(self.report, ['index.md'])
        self.assertEqual(before, self.report)
        self.assertEqual(files, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_batch_and_repeat(self):
        result = preview_removal(self.report, ['index.md', 'verse.md', 'index.md'])
        self.assertEqual(result['removed'], ['index.md', 'verse.md'])
        self.assertEqual(result['split_groups'], [])
        self.assertEqual(result['remaining_note_count'], 2)

    def test_all_removed(self):
        result = preview_removal(self.report, [n['id'] for n in self.report['notes']])
        self.assertEqual(result['components'], [])
        self.assertEqual(result['newly_isolated'], [])

    def test_unknown_exact_ids_rejected(self):
        for name in ['index', 'INDEX.md', '../index.md']:
            with self.assertRaises(ValueError):
                preview_removal(self.report, [name])

    def test_empty_preview(self):
        result = preview_removal(self.report, [])
        self.assertEqual(result['components'], self.report['components'])
        self.assertEqual(result['newly_isolated'], [])

    def test_redundant_connection_prevents_split(self):
        (self.root / 'verse.md').write_text('[[index]] [[chorus]]')
        result = preview_removal(analyze(self.root), ['index.md'])
        self.assertEqual(result['split_groups'], [])
        self.assertEqual(result['newly_isolated'], [])

    def test_ambiguous_link_not_reresolved(self):
        (self.root / 'one').mkdir()
        (self.root / 'two').mkdir()
        (self.root / 'one/draft.md').write_text('a')
        (self.root / 'two/draft.md').write_text('b')
        (self.root / 'private.md').write_text('[[draft]]')
        result = preview_removal(analyze(self.root), ['one/draft.md'])
        self.assertIn(['private.md'], result['components'])

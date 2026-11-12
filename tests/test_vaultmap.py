import json
from pathlib import Path
import tempfile
import unittest
from vaultmap import analyze, visible


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write(self, path, text):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')

    def test_empty(self):
        self.assertEqual(analyze(self.root)['notes'], [])

    def test_wiki_alias_heading(self):
        self.write('a.md', '[[b#Verse|draft]]')
        self.write('b.md', '# Verse')
        self.assertEqual(analyze(self.root)['links'], [{'source': 'a.md', 'target': 'b.md'}])

    def test_relative_urlencoded(self):
        self.write('poems/a.md', '[idea](../song%20idea.md)')
        self.write('song idea.md', 'hello')
        self.assertEqual(len(analyze(self.root)['links']), 1)

    def test_ambiguous(self):
        self.write('a.md', '[[draft]]')
        self.write('one/draft.md', 'one')
        self.write('two/draft.md', 'two')
        self.assertEqual(analyze(self.root)['unresolved'][0]['reason'], 'ambiguous')

    def test_local_precedence(self):
        self.write('one/a.md', '[[draft]]')
        self.write('one/draft.md', 'one')
        self.write('two/draft.md', 'two')
        self.assertEqual(analyze(self.root)['links'][0]['target'], 'one/draft.md')

    def test_missing(self):
        self.write('a.md', '[[absent]]')
        self.assertEqual(analyze(self.root)['unresolved'][0]['reason'], 'missing')

    def test_unsafe(self):
        self.write('a.md', '[x](../secret.md) [[/etc/passwd]]')
        self.assertTrue(all(x['reason'] == 'unsafe-path' for x in analyze(self.root)['unresolved']))

    def test_external_images_fragments_ignored(self):
        self.write('a.md', '[x](https://example.com) ![x](photo.md) ![[photo]] [x](#part)')
        self.assertEqual(analyze(self.root)['unresolved'], [])

    def test_code_comments_ignored(self):
        self.write('a.md', '<!-- [[a]] -->\n```md\n[[b]]\n```\n`[[c]]`\n~~~\n[[d]]\n~~~')
        self.assertEqual(analyze(self.root)['links'], [])
        self.assertEqual(analyze(self.root)['unresolved'], [])

    def test_hidden_ignored(self):
        self.write('.obsidian/private.md', 'private')
        self.write('.private.md', 'private')
        self.assertEqual(analyze(self.root)['notes'], [])

    def test_symlink_ignored(self):
        self.write('a.md', 'text')
        (self.root / 'linked.md').symlink_to(self.root / 'a.md')
        self.assertEqual(len(analyze(self.root)['notes']), 1)

    def test_duplicates_and_components(self):
        self.write('a.md', '[[b]]')
        self.write('b.md', 'text')
        self.write('c.md', 'text')
        report = analyze(self.root)
        self.assertEqual(report['exact_duplicates'], [['b.md', 'c.md']])
        self.assertEqual(report['components'], [['a.md', 'b.md'], ['c.md']])
        self.assertEqual(report['isolated'], ['c.md'])

    def test_deterministic_no_body(self):
        self.write('a.md', 'PRIVATE BODY DO NOT EXPORT')
        first = analyze(self.root)
        self.assertEqual(first, analyze(self.root))
        self.assertNotIn('PRIVATE BODY', json.dumps(first))

    def test_invalid_utf8_fails_closed(self):
        (self.root / 'a.md').write_bytes(b'\xff')
        with self.assertRaises(UnicodeError):
            analyze(self.root)

    def test_casefold(self):
        self.write('a.md', '[[POEM]]')
        self.write('Poem.md', 'text')
        self.assertEqual(len(analyze(self.root)['links']), 1)


if __name__ == '__main__':
    unittest.main()

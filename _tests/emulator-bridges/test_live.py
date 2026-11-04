import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from live import ROOT, fixture_content


class FixtureAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.content = self.root / 'witness.nro'
        self.content.write_bytes(b'original lawful fixture artifact')
        self.manifest = {'system': 'switch', 'content': 'witness.nro', 'license': 'CC0-1.0',
                         'fixture_sha256': hashlib.sha256(self.content.read_bytes()).hexdigest(),
                         'source_sha256': hashlib.sha256((ROOT / '_tests/live/emulator-family/switch.c').read_bytes()).hexdigest()}
        self.write_manifest()

    def write_manifest(self):
        (self.root / 'fixture.json').write_text(json.dumps(self.manifest))

    def test_verified_witness_content_is_selected(self):
        self.assertEqual(fixture_content(self.root, 'switch'), self.content.resolve())

    def test_changed_content_is_rejected(self):
        self.content.write_bytes(b'changed artifact')
        with self.assertRaisesRegex(ValueError, 'digest'):
            fixture_content(self.root, 'switch')

    def test_different_source_witness_is_rejected(self):
        self.manifest['source_sha256'] = '0' * 64
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'source differs'):
            fixture_content(self.root, 'switch')

    def test_switch_fixture_cannot_qualify_switch2(self):
        with self.assertRaisesRegex(ValueError, 'matching lawful'):
            fixture_content(self.root, 'switch2')

    def test_content_cannot_escape_artifact(self):
        with tempfile.NamedTemporaryFile() as outside:
            self.manifest['content'] = outside.name
            self.write_manifest()
            with self.assertRaisesRegex(ValueError, 'escapes'):
                fixture_content(self.root, 'switch')


if __name__ == '__main__':
    unittest.main()

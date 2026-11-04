import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from live import ROOT, fixture_content, linux_frontend, require_system
from native_build import build_command, emulator_binaries


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


class OunceFixtureAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.exefs = self.root / 'exefs'
        self.exefs.mkdir()
        (self.exefs / 'main').write_bytes(b'synthetic NSO admission fixture')
        (self.exefs / 'main.npdm').write_bytes(b'synthetic metadata admission fixture')
        self.config = self.root / 'emulator.ini'
        self.config.write_text('[Core]\nmemory_layout_mode=4\n')
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        self.manifest = {'system': 'switch2', 'content': 'exefs/main', 'source_license': 'CC0-1.0',
            'source_sha256': digest(ROOT / '_tests/live/emulator-family/switch.c'),
            'descriptor_sha256': digest(ROOT / '_tests/live/emulator-family/ounce-witness.npdm.json'),
            'emulator_config_sha256': digest(self.config),
            'libnx_ounce_revision': 'a04b88b3d3ed059963200d0a3d460754b2fe294e',
            'libnx_ounce_library_sha256': 'a' * 64,
            'members': {path.name: digest(path) for path in self.exefs.iterdir()}}
        self.write_manifest()

    def write_manifest(self):
        (self.root / 'fixture.json').write_text(json.dumps(self.manifest))

    def test_builder_manifest_shape_admits_the_whole_graph(self):
        self.assertEqual(fixture_content(self.root, 'switch2'), (self.exefs / 'main').resolve())

    def test_changed_metadata_is_not_hidden_by_an_unchanged_main(self):
        (self.exefs / 'main.npdm').write_bytes(b'replaced metadata')
        with self.assertRaisesRegex(ValueError, 'member digest'):
            fixture_content(self.root, 'switch2')

    def test_extra_unrecorded_member_is_rejected(self):
        (self.exefs / 'unrecorded').write_bytes(b'extra content')
        with self.assertRaisesRegex(ValueError, 'two-member'):
            fixture_content(self.root, 'switch2')

    def test_changed_config_is_rejected(self):
        self.config.write_text('[Core]\nmemory_layout_mode=0\n')
        with self.assertRaisesRegex(ValueError, 'config digest'):
            fixture_content(self.root, 'switch2')

    def test_wrong_descriptor_is_rejected(self):
        self.manifest['descriptor_sha256'] = '0' * 64
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'descriptor differs'):
            fixture_content(self.root, 'switch2')


class RyubingAdmissionTests(unittest.TestCase):
    def test_ryubing_switch2_is_rejected(self):
        require_system('ryubing', 'switch')
        with self.assertRaisesRegex(ValueError, 'does not implement'):
            require_system('ryubing', 'switch2')
        with self.assertRaisesRegex(ValueError, 'does not implement'):
            require_system('ryubing', '3ds')

    def test_ryubing_artifacts_use_own_recipe_and_frontend(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = Path(temporary)
            command = build_command('ryubing', payload, 2)
            self.assertEqual(Path(command[2]), ROOT / 'adapters/ryujinx-family/build.py')
            self.assertEqual(command[3:], ['--fork', 'ryubing', '--output', str(payload), '--jobs', '2'])
            # A successful Eden binary or bridge DLL cannot qualify a Ryubing build.
            (payload / 'eden-sdl').touch()
            (payload / 'emucap-native.dll').touch()
            self.assertEqual(emulator_binaries(payload, 'ryubing'), [])
            binary = payload / 'Ryujinx'
            binary.touch()
            self.assertEqual(emulator_binaries(payload, 'ryubing'), [binary])
            self.assertEqual(linux_frontend(payload, 'ryubing'), binary)


if __name__ == '__main__':
    unittest.main()

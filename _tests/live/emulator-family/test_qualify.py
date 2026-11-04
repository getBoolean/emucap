"""Pixel witness admission tests; these synthetic images do not qualify an emulator."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

spec = importlib.util.spec_from_file_location('qualify', Path(__file__).with_name('qualify.py'))
qualify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualify)


class PixelAdmissionTests(unittest.TestCase):
    def test_cleanup_removes_read_only_staged_members(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / 'owned-runtime'
            home.mkdir()
            member = home / 'main'
            member.write_bytes(b'owned staged content')
            member.chmod(0o400)
            qualify.remove_runtime_home(home)
            self.assertFalse(home.exists())

    def test_composite_media_requires_explicit_approval(self):
        plan = {'indirect_media': {'state': 'review_required'}, 'next_action': {
            'then_call': {'arguments': {'indirect_media_approval': {'digest': 'fixture'}}}}}
        with self.assertRaisesRegex(RuntimeError, 'explicit reviewed-media approval'):
            qualify.composite_approval(plan, False)
        self.assertEqual(qualify.composite_approval(plan, True), {'digest': 'fixture'})
        self.assertIsNone(qualify.composite_approval({}, False))

    def test_touch_qualification_requires_the_expected_native_contract(self):
        valid = {'touch_capability': {'ports': [0], 'width': 320, 'height': 240,
                 'contacts': 1, 'coordinate_space': 'touchscreen'},
                 'methods': ['hold_touch', 'release_touch']}
        self.assertEqual(qualify.require_touch(valid, '3ds')['width'], 320)
        for status in ({}, {'touch_capability': valid['touch_capability'], 'methods': []},
                       dict(valid, touch_capability=dict(valid['touch_capability'], width=256))):
            with self.assertRaisesRegex(RuntimeError, 'touchscreen capability'):
                qualify.require_touch(status, '3ds')
    def test_artifacts_exclude_private_auth_and_redact_runtime_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, output = root / 'private', root / 'artifact'
            generation = home / 'sessions/123/generations/launch-test'
            generation.mkdir(parents=True)
            output.mkdir()
            (generation / 'auth').write_text('private-network-credential')
            native_log = generation / 'emulators/eden-family/log/eden_log.txt'
            native_log.parent.mkdir(parents=True)
            native_log.write_text('native startup diagnostics')
            (native_log.parent.parent / 'private-user-data').write_text('do not collect')
            (generation / 'link.json').write_text(json.dumps({
                'launch_id': 'launch-test', 'lease': {'control_session_key': 'private-control-key'},
                'last_identity': {'session_token': 'private-network-credential', 'system': '3ds'}}))
            qualify.collect_runtime_evidence(home, output)
            artifact = json.loads((output / 'runtime-link.json').read_text())
            self.assertEqual(artifact['launch_id'], 'launch-test')
            self.assertEqual(artifact['last_identity'], {'system': '3ds'})
            self.assertNotIn('private-', (output / 'runtime-link.json').read_text())
            self.assertFalse((output / 'auth').exists())
            self.assertEqual((output / 'native-user.log').read_text(), 'native startup diagnostics')
            self.assertFalse((output / 'private-user-data').exists())

    def test_switch_requires_native_border_bounds_instead_of_clamped_edges(self):
        valid = {'touch_capability': {'ports': [0], 'width': 1280, 'height': 720,
                 'contacts': 1, 'coordinate_space': 'touchscreen',
                 'bounds': {'x_min': 15, 'x_max': 1264, 'y_min': 15, 'y_max': 704}},
                 'methods': ['hold_touch', 'release_touch']}
        self.assertEqual(qualify.require_touch(valid, 'switch')['bounds']['x_min'], 15)
        missing = dict(valid, touch_capability=dict(valid['touch_capability']))
        missing['touch_capability'].pop('bounds')
        with self.assertRaisesRegex(RuntimeError, 'coordinate bounds'):
            qualify.require_touch(missing, 'switch')

    def test_ryubing_bounds_are_full_screen_and_do_not_relax_eden_bounds(self):
        status = {'touch_capability': {'ports': [0], 'width': 1280, 'height': 720,
                  'contacts': 1, 'coordinate_space': 'touchscreen',
                  'bounds': {'x_min': 0, 'x_max': 1279, 'y_min': 0, 'y_max': 719}},
                  'methods': ['hold_touch', 'release_touch']}
        self.assertEqual(qualify.require_touch(status, 'switch', 'ryubing')['bounds']['x_max'], 1279)
        with self.assertRaisesRegex(RuntimeError, 'coordinate bounds'):
            qualify.require_touch(status, 'switch', 'eden')
        with self.assertRaisesRegex(RuntimeError, 'Switch 1 only'):
            qualify.require_touch(status, 'switch2', 'ryubing')

    def image(self, path, identity=1, magic=0x454d5543):
        image = Image.new('RGB', (1280, 720), (48, 48, 48))
        draw = ImageDraw.Draw(image)
        for y, value in zip((16, 40, 64, 88, 112, 136),
                            (magic, 19, 1, 24000, 0xffffffff, identity)):
            for bit in range(32):
                x = 16 + bit * 8
                draw.rectangle((x, y, x + 7, y + 7), fill='white' if value & (1 << bit) else 'black')
        image.save(path)

    def test_decodes_guest_pixels_and_rejects_switch1_as_switch2(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'guest.png'
            self.image(path)
            value = qualify.decode(path, 'switch')
            self.assertEqual((value['frame'], value['buttons'], value['stick'], value['touch']),
                             (19, 1, 24000, 0xffffffff))
            with self.assertRaisesRegex(RuntimeError, 'target identity mismatch'):
                qualify.decode(path, 'switch2')

    def test_rejects_an_unrelated_screenshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'unrelated.png'
            self.image(path, magic=0)
            with self.assertRaisesRegex(RuntimeError, 'magic missing'):
                qualify.decode(path, 'switch')

    def test_ctr_top_screen_alone_is_not_combined_screen_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cropped.png'
            self.image(path, identity=3)
            with Image.open(path) as image:
                cropped = image.crop((0, 0, 400, 240))
            cropped.save(path)
            with self.assertRaisesRegex(RuntimeError, 'capture dimensions'):
                qualify.decode(path, '3ds')


if __name__ == '__main__':
    unittest.main()

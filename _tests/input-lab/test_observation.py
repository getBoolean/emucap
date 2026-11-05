"""Contract tests through the native renderer, with an independent Python decoder."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from observation import decode, require_state, require_handheld_ui


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.binary = cls.root / ('render.exe' if os.name == 'nt' else 'render')
        subprocess.run([os.environ.get('CC', 'clang'), '-std=c11', '-Wall', '-Wextra',
                        '-Werror', str(Path(__file__).with_name('host_render.c')),
                        '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def render(self, width=160, height=144):
        path = self.root / 'frame.ppm'
        subprocess.run([str(self.binary), str(path), str(width), str(height)], check=True)
        return path

    def test_smallest_screen_round_trip_native_values_and_edges(self):
        observed = decode(self.render(), 160, 144)
        self.assertEqual(observed['sequence'], 3)
        self.assertEqual(observed['buttons'], 0x8000000000000009)
        self.assertEqual(observed['pressed_seen'], 0x800000000000000b)
        self.assertEqual(observed['released_seen'], 2)
        self.assertEqual(observed['axes'], [-32768, 32767, -123, 456])
        self.assertEqual(observed['triggers'], [0, 32767])
        self.assertEqual(observed['touch'], [319, 239])
        self.assertEqual(observed['native_buttons'], 0x1122334455667788)
        self.assertEqual(observed['port'], 3)

    def test_scaled_capture(self):
        from PIL import Image
        path = self.render(400, 240)
        with Image.open(path) as image:
            image.resize((800, 480), Image.Resampling.NEAREST).save(self.root / 'scaled.png')
        self.assertEqual(decode(self.root / 'scaled.png', 400, 240)['axes'][0], -32768)

    def test_valid_telemetry_cannot_hide_a_blank_handheld_viewer(self):
        from PIL import Image
        path = self.render(240, 160)
        require_handheld_ui(path, 240)
        with Image.open(path) as image:
            image.paste((16, 29, 48), (0, 0, 240, 90))
            image.save(self.root / 'blank-viewer.png')
        self.assertEqual(decode(self.root / 'blank-viewer.png', 240, 160)['sequence'], 3)
        with self.assertRaisesRegex(ValueError, 'title/sample labels'):
            require_handheld_ui(self.root / 'blank-viewer.png', 240)

    def test_wrong_target_and_build_rejected(self):
        path = self.render()
        with self.assertRaisesRegex(ValueError, 'target'):
            decode(path, 160, 144, target=2)
        with self.assertRaisesRegex(ValueError, 'build identity'):
            decode(path, 160, 144, build_id='11' * 16)

    def test_sequence_rollover_accepts_fresh_sample(self):
        observed = decode(self.render(), 160, 144)
        observed['sequence'] = 0
        require_state(observed, {'buttons': observed['buttons']}, after=0xffffffff)
        with self.assertRaises(AssertionError):
            require_state(observed, {'axes': [0]}, after=0xffffffff)

    def test_corrupt_bit_rejected(self):
        from PIL import Image
        path = self.render()
        with Image.open(path) as image:
            image = image.convert('RGB')
            # Word 8 is a stick pair; flip one data bit without fixing its checksum.
            x, y = 9, 144 - 40 + 4 * 2 + 1
            value = image.getpixel((x, y))[0]
            image.putpixel((x, y), (0, 0, 0) if value else (255, 255, 255))
            image.save(self.root / 'corrupt.png')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            decode(self.root / 'corrupt.png', 160, 144)

    def test_oracle_rejects_wrong_button_axis_touch_port_and_stale_sample(self):
        observed = decode(self.render(), 160, 144)
        expected = dict(buttons=observed['buttons'], axes=observed['axes'],
                        triggers=observed['triggers'], touch=observed['touch'], port=3)
        require_state(observed, expected, after=2)
        for field, wrong in [('buttons', 8), ('axes', [32767, -32768, -123, 456]),
                             ('triggers', [32767, 0]), ('touch', [239, 319]), ('port', 0)]:
            with self.subTest(field=field), self.assertRaises(AssertionError):
                require_state(observed, dict(expected, **{field: wrong}), after=2)
        with self.assertRaisesRegex(AssertionError, 'stale'):
            require_state(observed, expected, after=3)


if __name__ == '__main__':
    unittest.main()

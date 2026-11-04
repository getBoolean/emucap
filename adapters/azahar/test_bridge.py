import ctypes as C
import unittest
import io
from unittest import mock
from bridge import Bridge, png, serve

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge.__new__(Bridge)
        self.bridge.buttons = set()
        self.bridge.touch = None
        self.bridge.frame = 0
        self.bridge.image = None
        self.bridge.failure = None

    def test_input_replacement_and_release(self):
        b = self.bridge
        b.request('set_input', {'buttons': ['a'], 'touch': [0, 0]})
        self.assertEqual(b.input(0, 1, 0, 8), 1)
        self.assertEqual(b.input(0, 6, 0, 2), 1)
        self.assertGreater(b.input(0, 6, 0, 1), 0)
        b.request('set_input', {})
        self.assertEqual(b.input(0, 1, 0, 8), 0)
        self.assertEqual(b.input(0, 6, 0, 2), 1)
        b.request('touch', {'release': True})
        self.assertEqual(b.input(0, 6, 0, 2), 0)

    def test_invalid_and_unsupported(self):
        for params in ({'buttons': ['invalid']}, {'touch': [320, 0]},
                       {'buttons': 'a'}, {'buttons': [[]]}, {'touch': 1},
                       {'touch': [True, 0]}, {'touch': [0.5, 1]}):
            with self.assertRaises(ValueError):
                self.bridge.request('set_input', params)
        with self.assertRaises(NotImplementedError):
            self.bridge.request('step_instructions', {})
        with self.assertRaises(RuntimeError):
            self.bridge.request('screenshot', {})

    def test_video_copies_pitch_and_duplicate(self):
        b = self.bridge
        b.pixel_format = 1
        pixels = C.create_string_buffer(bytes([0, 0, 255, 0, 99, 99, 99, 99]))
        b.video(C.addressof(pixels), 1, 1, 8)
        self.assertEqual(b.image, (1, 1, png(1, 1, [bytes([255, 0, 0])])))
        b.video(None, 1, 1, 8)
        self.assertIsNotNone(b.image)

    def test_invalid_video_does_not_read_native_memory(self):
        self.bridge.pixel_format = 1
        for width, height, pitch in ((0, 1, 4), (1, 0, 4), (2, 1, 4)):
            self.bridge.video(1, width, height, pitch)
            self.assertIsNotNone(self.bridge.failure)
            self.assertIsNone(self.bridge.image)

    def test_pixel_output_bound_and_controller_axis_validation(self):
        with mock.patch('bridge.MAX_PNG_BYTES', 1):
            with self.assertRaises(RuntimeError):
                png(1, 1, [b'\x00\x00\x00'])
        self.bridge.request('set_input', {'axes': {'stick_x': -32767, 'cstick_y': 32767}})
        self.assertEqual(self.bridge.input(0, 5, 0, 0), -32767)
        self.assertEqual(self.bridge.input(0, 5, 1, 1), 32767)
        for axes in ({'unknown': 1}, {'stick_x': True}, {'stick_x': 32768}):
            with self.assertRaises(ValueError):
                self.bridge.request('set_input', {'axes': axes})
        self.bridge.request('set_input', {})
        self.assertEqual(self.bridge.input(0, 5, 0, 0), 0)

    def test_bad_request_params_retain_next_frame_boundary(self):
        output = io.BytesIO()
        serve(self.bridge, io.BytesIO(b'{"v":1,"id":1,"method":"status","params":[]}\n'
                                     b'{"v":1,"id":2,"method":"status","params":{}}\n'), output)
        import json
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertFalse(replies[0]['ok'])
        self.assertTrue(replies[1]['ok'])

if __name__ == '__main__':
    unittest.main()

import ctypes as C
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('software_bridge', pathlib.Path(__file__).with_name('bridge.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InputTests(unittest.TestCase):
    def bridge(self, fork, system):
        bridge = module.Bridge.__new__(module.Bridge)
        bridge.configure({'family': 'software-libretro', 'fork': fork, 'systems': [system]})
        bridge.buttons, bridge.axes, bridge.touch, bridge.failure = set(), {}, None, None
        return bridge

    def test_gba_atomic_rejection_and_release(self):
        b = self.bridge('mgba', 'gba')
        b.request('set_input', {'buttons': ['a', 'l']})
        for invalid in ({'buttons': ['x']}, {'buttons': ['b'], 'touch': [0, 0]},
                        {'buttons': [], 'axes': {'stick_x': 1}}, {'port': 1}):
            with self.assertRaises((ValueError, NotImplementedError)):
                b.request('set_input', invalid)
            self.assertEqual(b.input(0, 1, 0, 256), (1 << 8) | (1 << 10))
        with self.assertRaises(NotImplementedError):
            b.request('touch', {'release': True})
        b.request('set_input', {'buttons': []})
        self.assertEqual(b.input(0, 1, 0, 256), 0)

    def test_ds_touch_edges_inverse_and_persistence(self):
        b = self.bridge('melonds', 'nds')
        for x, y in ((0, 0), (255, 0), (0, 191), (255, 191), (128, 96)):
            b.request('touch', {'x': x, 'y': y})
            px, py = b.input(0, 6, 0, 0), b.input(0, 6, 0, 1)
            self.assertEqual((int((px + 32767) * 256 / 65534),
                              int((py + 32767) * 384 / 65534) - 192), (x, y))
            b.request('set_input', {'buttons': ['x']})
            self.assertEqual(b.input(0, 6, 0, 2), 1)
        b.request('touch', {'release': True})
        self.assertEqual(b.input(0, 6, 0, 2), 0)
        self.assertEqual(b.input(1, 1, 0, 9), 0)

    def test_geometry_fails_closed(self):
        b = self.bridge('melonds', 'nds')
        with self.assertRaises(ValueError):
            b.set_geometry(module.abi.Geometry(512, 192, 512, 192, 0))
        with self.assertRaises(ValueError):
            b.request('touch', {'x': 256, 'y': 0})
        with self.assertRaises(NotImplementedError):
            b.request('touch', {'x': 1, 'y': 1, 'frames': 1})


if __name__ == '__main__':
    unittest.main()

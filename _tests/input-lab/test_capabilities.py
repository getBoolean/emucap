"""A missing capability must fail qualification instead of reducing its scope."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('capability_runner', Path(__file__).with_name('qualify.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class CapabilityTests(unittest.TestCase):
    def test_required_input_surfaces_cannot_disappear(self):
        buttons = 'a b select start up down left right l r'.split()
        for system in ('gba', 'nds', '3ds', 'switch', 'switch2'):
            status = {'input_buttons': {'buttons': buttons + (['x', 'y'] if system == 'nds' else [])}}
            if system != 'gba':
                status['touch_capability'] = {'width': 256}
            if system in ('3ds', 'switch', 'switch2'):
                status['input_axes'] = {'ports': [0]}
            runner.validate_capabilities(status, system)
            for field in ('touch_capability', 'input_axes'):
                wrong = dict(status)
                if field in wrong:
                    del wrong[field]
                else:
                    wrong[field] = {'unexpected': True}
                with self.assertRaisesRegex(RuntimeError, 'capability mismatch'):
                    runner.validate_capabilities(wrong, system)
            if system in ('gba', 'nds'):
                wrong = dict(status, input_buttons={'buttons': status['input_buttons']['buttons'][1:]})
                with self.assertRaisesRegex(RuntimeError, 'button capability mismatch'):
                    runner.validate_capabilities(wrong, system)

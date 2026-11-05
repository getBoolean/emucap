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
            expected = buttons + (['x', 'y'] if system in ('nds', '3ds') else [])
            if system == '3ds':
                expected += ['zl', 'zr']
            elif system in ('switch', 'switch2'):
                expected = 'a b x y lstick rstick l r zl zr plus minus left up right down'.split()
            status = {'input_buttons': {'buttons': expected}}
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
            for missing in expected:
                wrong = dict(status, input_buttons={'buttons': [b for b in expected if b != missing]})
                with self.assertRaisesRegex(RuntimeError, 'button capability mismatch'):
                    runner.validate_capabilities(wrong, system)
            if system in ('switch', 'switch2'):
                runner.validate_capabilities(dict(status, input_buttons=expected + ['sl', 'sr']), system)

    def test_rail_buttons_follow_the_native_family(self):
        buttons = 'a b x y lstick rstick l r zl zr plus minus left up right down'.split()
        status = {'adapter': 'eden-family-native', 'input_buttons': buttons,
                  'touch_capability': {'width': 1280}, 'input_axes': {'ports': [0]}}
        runner.validate_capabilities(status, 'switch')
        status['adapter'] = 'ryujinx-family-native'
        with self.assertRaisesRegex(RuntimeError, 'button capability mismatch'):
            runner.validate_capabilities(status, 'switch')
        status['input_buttons'] = buttons + ['sl', 'sr']
        runner.validate_capabilities(status, 'switch')
        for missing in ('y', 'sl', 'sr'):
            wrong = dict(status, input_buttons=[b for b in status['input_buttons'] if b != missing])
            with self.assertRaisesRegex(RuntimeError, 'button capability mismatch'):
                runner.validate_capabilities(wrong, 'switch')

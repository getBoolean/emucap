import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import native_build
import live
from fast import ryujinx_abi_command

HERE = Path(__file__).resolve().parent


class QualificationFailureTests(unittest.TestCase):
    def test_ryubing_live_lane_forwards_its_linux_memory_mode_and_runtime_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = root / 'native'
            (native / 'payload').mkdir(parents=True)
            (native / 'payload/Ryujinx').touch()
            (native / 'native-build-results.json').write_text(json.dumps({'status': 'passed', 'fork': 'ryubing'}))
            evidence = root / 'evidence'
            content = root / 'witness.nro'

            def guest(command, **kwargs):
                config = Path(command[command.index('--config') + 1])
                self.assertEqual(json.loads(config.read_text()), {'memory_manager_mode': 'SoftwarePageTable'})
                self.assertEqual(kwargs['env']['DOTNET_EnableAlternateStackCheck'], '1')
                output = Path(command[command.index('--output') + 1])
                output.mkdir()
                (output / 'result.json').write_text('{"status":"passed"}')
                return subprocess.CompletedProcess(command, 0)

            with patch.object(sys, 'argv', ['live.py', '--fork', 'ryubing', '--system', 'switch',
                    '--native', str(native), '--fixture', str(root / 'fixture'), '--output', str(evidence)]), \
                    patch.object(live, 'fixture_content', return_value=content), \
                    patch.object(live.subprocess, 'run', side_effect=guest) as run:
                live.main()
                run.assert_called_once()
            self.assertTrue(json.loads((evidence / 'live-job-results.json').read_text())['live_qualified'])

    def test_switch2_requires_explicit_approval_before_artifact_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            process = subprocess.run([sys.executable, str(HERE / 'live.py'), '--fork', 'eden-nx2',
                '--system', 'switch2', '--native', str(root / 'native'),
                '--fixture', str(root / 'fixture'), '--output', str(root / 'evidence')],
                capture_output=True, text=True, timeout=30)
            self.assertNotEqual(process.returncode, 0)
            result = json.loads((root / 'evidence/live-job-results.json').read_text())
            self.assertEqual(result['status'], 'blocked')
            self.assertFalse(result['live_qualified'])
            self.assertIn('explicit reviewed', result['error'])
            self.assertNotIn('command', result)

    def test_missing_ryujinx_compiler_is_fatal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(FileNotFoundError):
                subprocess.run(ryujinx_abi_command(str(root / 'no-cxx'), root / 'bridge.dll', root),
                               check=True, capture_output=True, timeout=10)

    def test_unsupported_ryubing_build_host_records_failure_without_building(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(sys, 'argv', ['native_build.py', '--fork', 'ryubing', '--evidence', str(root)]), \
                    patch.object(native_build.platform, 'system', return_value='Darwin'), \
                    patch.object(native_build.platform, 'platform', return_value='unsupported-test-host'), \
                    patch.object(native_build.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'Windows/Linux x86_64'):
                    native_build.main()
                run.assert_not_called()
            result = json.loads((root / 'native-build-results.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertFalse(result['live_qualified'])

    def test_ryubing_switch2_is_blocked_before_artifact_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            process = subprocess.run([sys.executable, str(HERE / 'live.py'), '--fork', 'ryubing',
                                      '--system', 'switch2', '--native', str(root / 'native'),
                                      '--fixture', str(root / 'fixture'), '--output', str(root / 'evidence')],
                                     capture_output=True, text=True, timeout=30)
            self.assertNotEqual(process.returncode, 0)
            result = json.loads((root / 'evidence/live-job-results.json').read_text())
            self.assertEqual(result['status'], 'blocked')
            self.assertIn('does not implement', result['error'])
            self.assertNotIn('command', result)

    def test_missing_compiler_fails_before_worker_tests(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = Path(temporary) / 'evidence'
            process = subprocess.run([sys.executable, str(HERE / 'fast.py'), '--evidence', str(evidence),
                                      '--cc', str(Path(temporary) / 'no-compiler')],
                                     capture_output=True, text=True, timeout=30)
            self.assertNotEqual(process.returncode, 0)
            result = json.loads((evidence / 'fast-results.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertFalse(result.get('fixture', {}).get('loaded', False))
            self.assertEqual(result['checks'], [])

    def test_missing_live_assets_are_blocked_and_nonzero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            process = subprocess.run([sys.executable, str(HERE / 'live.py'), '--fork', 'azahar',
                                      '--system', '3ds', '--native', str(root / 'missing-native'),
                                      '--fixture', str(root / 'missing-fixture'),
                                      '--output', str(root / 'evidence')],
                                     capture_output=True, text=True, timeout=30)
            self.assertNotEqual(process.returncode, 0)
            result = json.loads((root / 'evidence/live-job-results.json').read_text())
            self.assertEqual(result['status'], 'blocked')
            self.assertFalse(result['live_qualified'])


if __name__ == '__main__':
    unittest.main()

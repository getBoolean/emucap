import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class QualificationFailureTests(unittest.TestCase):
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

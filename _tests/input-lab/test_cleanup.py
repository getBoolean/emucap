"""Failed qualification must still reap its process and retain terminal evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('input_lab_runner', Path(__file__).with_name('qualify.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class CleanupTests(unittest.TestCase):
    def exercise(self, *, fail_stop=False, fail_evidence=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        content = root / 'input-lab.nro'
        content.write_bytes(b'original-test-content')
        (root / 'fixture.json').write_text(json.dumps({'system': 'switch', 'build_id': '00'*16,
            'content_sha256': hashlib.sha256(content.read_bytes()).hexdigest()}), encoding='utf-8')
        launch = root / 'launch.json'
        launch.write_text(json.dumps({'system': 'switch', 'content_path': str(content)}), encoding='utf-8')
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self.addCleanup(lambda: (child.terminate(), child.wait()) if child.poll() is None else None)

        class Endpoint:
            def __init__(self, *args):
                pass

            def initialize(self):
                pass

            def tool(self, name, arguments=None):
                if name == 'launch_plan':
                    return {}
                if name == 'launch':
                    return {'launched': True, 'runtime_instance': {'launch_id': 'owned-test'}}
                if name == 'status':
                    return {'contracts': {'state': 'invalid'}}
                if name == 'stop':
                    if fail_stop:
                        raise RuntimeError('stop transport failed')
                    return {'stopped': True, 'status': 'completed'}
                raise AssertionError(name)

            def close(self):
                child.terminate()
                child.wait(timeout=10)

        argv = ['qualify.py', '--mcp', sys.executable, '--launch-json', str(launch), '--output', str(root/'live')]
        evidence = RuntimeError('evidence disk error') if fail_evidence else None
        with patch.object(sys, 'argv', argv), patch.object(runner, 'McpProcess', Endpoint), \
                patch.object(runner, 'collect_runtime_evidence', side_effect=evidence):
            with self.assertRaises(RuntimeError):
                runner.main()
        return child, root/'live/result.json'

    def test_stop_failure_still_reaps_owned_process(self):
        child, result = self.exercise(fail_stop=True)
        self.assertIsNotNone(child.poll(), 'stop failure leaked the MCP process')
        record = json.loads(result.read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'failed')
        self.assertIn('stop transport failed', record['cleanup_error'])

    def test_evidence_failure_retains_terminal_result(self):
        child, result = self.exercise(fail_evidence=True)
        self.assertIsNotNone(child.poll())
        self.assertTrue(result.is_file(), 'evidence error discarded terminal result')
        record = json.loads(result.read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'failed')
        self.assertIn('evidence disk error', record['cleanup_error'])


if __name__ == '__main__':
    unittest.main()

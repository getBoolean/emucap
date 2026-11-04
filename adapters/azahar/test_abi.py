import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tests.build_fixture import build_fixture


class NativeAbiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls.temporary.name)
        cls.library = build_fixture(cls.root)
        cls.rom = cls.root / 'fixture.3dsx'
        cls.rom.write_bytes(b'lawful synthetic ABI fixture')

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_worker(self, mode='', requests=None):
        log = self.root / 'lifecycle.log'
        log.unlink(missing_ok=True)
        env = dict(os.environ, EMUCAP_FAKE_MODE=mode, EMUCAP_FAKE_LOG=str(log))
        commands = requests or [{'v': 1, 'id': 1, 'method': 'hello', 'params': {}},
                                {'v': 1, 'id': 2, 'method': 'run_frames', 'params': {'count': 1}},
                                {'v': 1, 'id': 3, 'method': 'screenshot', 'params': {}}]
        process = subprocess.run([sys.executable, '-I', '-u', str(pathlib.Path(__file__).with_name('bridge.py')),
                                  '--core', str(self.library), '--rom', str(self.rom),
                                  '--directory', str(self.root / 'data')],
                                 input=''.join(json.dumps(command) + '\n' for command in commands),
                                 capture_output=True, text=True, env=env, timeout=5)
        return process, log.read_text().splitlines() if log.exists() else []

    def test_native_lifecycle_and_diagnostics_channel(self):
        process, stages = self.run_worker()
        self.assertEqual(process.returncode, 0, process.stderr)
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual([reply['id'] for reply in replies], [1, 2, 3])
        self.assertEqual(replies[0]['result']['protocol_version'], 1)
        self.assertIn('png_base64', replies[2]['result'])
        self.assertIn('native diagnostic', process.stderr)
        self.assertEqual(stages, ['init', 'load', 'run', 'unload', 'deinit'])

    def test_rejected_load_deinitializes_without_unload(self):
        process, stages = self.run_worker('reject_load')
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(stages, ['init', 'load', 'deinit'])

    def test_invalid_api_and_fullpath_fail_before_init(self):
        for mode in ('bad_version', 'bad_fullpath'):
            with self.subTest(mode=mode):
                process, stages = self.run_worker(mode)
                self.assertNotEqual(process.returncode, 0)
                self.assertEqual(stages, [])

    def test_shutdown_latches_terminal_failure(self):
        process, stages = self.run_worker('shutdown')
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertFalse(replies[1]['ok'])
        self.assertIn('shutdown', replies[1]['error']['message'].lower())
        self.assertEqual(stages[-2:], ['unload', 'deinit'])

    def test_partial_initialization_and_callback_exception_are_safe(self):
        process, stages = self.run_worker('init_shutdown')
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(stages, ['init', 'deinit'])
        process, stages = self.run_worker('callback_failure')
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertFalse(replies[1]['ok'])
        self.assertIn('Native callback failed', replies[1]['error']['message'])
        self.assertEqual(stages[-2:], ['unload', 'deinit'])

    def test_malformed_request_does_not_corrupt_next_reply(self):
        process, _ = self.run_worker(requests=[[], {'v': 1, 'id': 7, 'method': 'status', 'params': {}}])
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertFalse(replies[0]['ok'])
        self.assertTrue(replies[1]['ok'])
        self.assertEqual(replies[1]['id'], 7)

    def test_request_bytes_are_bounded_before_json_allocation(self):
        process, stages = self.run_worker(requests=[{'v': 1, 'id': 1, 'method': 'status',
                                                   'params': {'padding': 'x' * 65536}}])
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(process.stdout, '')
        self.assertIn('Oversized or truncated', process.stderr)
        self.assertEqual(stages[-2:], ['unload', 'deinit'])

    def test_close_is_idempotent_after_successful_load(self):
        log = self.root / 'double-close.log'
        log.unlink(missing_ok=True)
        script = ("import sys;sys.path.insert(0,sys.argv[1]);from bridge import Bridge;"
                  "bridge=Bridge(*sys.argv[2:]);bridge.close();bridge.close()")
        process = subprocess.run([sys.executable, '-I', '-c', script,
                                  str(pathlib.Path(__file__).parent), str(self.library),
                                  str(self.rom), str(self.root / 'data')],
                                 capture_output=True, text=True, timeout=5,
                                 env=dict(os.environ, EMUCAP_FAKE_LOG=str(log)))
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(log.read_text().splitlines(), ['init', 'load', 'unload', 'deinit'])


if __name__ == '__main__':
    unittest.main()

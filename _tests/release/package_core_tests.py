"""Extracted Azahar payload boundaries and actual stdlib worker preflight."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

import package_core


class AzaharPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.host = self.root / 'target/release/emucap-azahar.exe'
        self.host.parent.mkdir(parents=True)
        self.host.write_bytes(b'host fixture')
        self.worker = self.root / 'adapters/azahar/bridge.py'
        self.worker.parent.mkdir(parents=True)
        source = Path(__file__).resolve().parents[2] / 'adapters/azahar/bridge.py'
        shutil.copy2(source, self.worker)

    def test_payload_records_worker_digest_and_external_dependencies(self):
        payload = package_core.azahar_payload(self.root, '.exe')
        self.assertEqual(payload['resources'], {
            'adapters/azahar/bridge.py': hashlib.sha256(self.worker.read_bytes()).hexdigest()})
        self.assertEqual(payload['python'], {'minimum_version': '3.12', 'bundled': False})
        self.assertEqual(payload['core'], {'bundled': False, 'build_profile_required': True})

    def test_missing_worker_is_a_package_failure(self):
        self.worker.unlink()
        with self.assertRaisesRegex(RuntimeError, 'bridge.py'):
            package_core.azahar_payload(self.root, '.exe')

    def test_missing_host_is_a_package_failure(self):
        self.host.unlink()
        with self.assertRaisesRegex(RuntimeError, 'emucap-azahar.exe'):
            package_core.azahar_payload(self.root, '.exe')

    def test_extracted_worker_runs_without_site_packages_and_rejects_missing_core(self):
        result = package_core.smoke_azahar_worker(self.root, self.root / 'scratch')
        self.assertEqual(result['worker_help'], 'passed')
        self.assertEqual(result['missing_core'], 'rejected')
        self.assertEqual(result['proof_level'], 'extracted-worker-preflight')
        self.assertFalse((self.root / 'adapters/azahar/build').exists())

    def test_broken_extracted_worker_fails_preflight(self):
        self.worker.write_text('import unavailable_emucap_package_dependency\n')
        with self.assertRaisesRegex(RuntimeError, 'worker help'):
            package_core.smoke_azahar_worker(self.root, self.root / 'scratch')


if __name__ == '__main__':
    unittest.main()

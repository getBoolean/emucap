"""Exact source preservation and shared maintained-descriptor admission."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('shared_build_support', ROOT / 'adapters/_common/build_support.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


def output(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def run(*args, cwd=None):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True, capture_output=True)


class BuildSupportTests(unittest.TestCase):
    def test_all_maintained_descriptors_have_distinct_pins_and_explicit_systems(self):
        self.assertEqual(set(support.SOURCE_DESCRIPTORS),
                         {'azahar', 'eden', 'eden-nx2', 'eglantine', 'ryubing', 'melonds', 'mgba'})
        for fork in support.SOURCE_DESCRIPTORS:
            descriptor = support.maintained_source(fork)
            self.assertEqual(descriptor['fork'], fork)
            self.assertRegex(descriptor['revision'], r'^[0-9a-f]{40}$')
            self.assertTrue(descriptor['repository'].startswith('https://'))
            self.assertTrue(descriptor['systems'])

    def test_exact_patch_accepts_crlf_and_preserves_unrelated_files(self):
        with tempfile.TemporaryDirectory(prefix='emucap-shared-patch-') as directory:
            root = Path(directory)
            run('git', 'init', '-q', root)
            (root / 'a.txt').write_bytes(b'before\n')
            run('git', 'add', 'a.txt', cwd=root)
            run('git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid',
                'commit', '-qm', 'fixture', cwd=root)
            patch = root / 'selected.patch'
            patch.write_bytes(b'--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-before\n+after\n')
            (root / 'unrelated.txt').write_bytes(b'preserve')
            (root / 'a.txt').write_bytes(b'after\r\n')
            support.verify_applied_patch(root, patch, output=output, run=run)
            self.assertEqual((root / 'unrelated.txt').read_bytes(), b'preserve')
            (root / 'a.txt').write_bytes(b'after\nhidden edit\n')
            with self.assertRaisesRegex(RuntimeError, 'differs from'):
                support.verify_applied_patch(root, patch, output=output, run=run)
            self.assertEqual((root / 'a.txt').read_bytes(), b'after\nhidden edit\n')

    def test_duplicate_and_unsafe_patch_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patch = root / 'selected.patch'
            for paths, error in [(['a', 'a'], 'exactly once'), (['../outside'], 'unsafe'),
                                 (['/outside'], 'unsafe'), (['C:outside'], 'unsafe'),
                                 (['a\\..\\outside'], 'unsafe')]:
                patch.write_text(''.join('+++ b/' + name + '\n' for name in paths))
                with self.subTest(paths=paths), self.assertRaisesRegex(RuntimeError, error):
                    support.verify_applied_patch(root, patch,
                        output=lambda *args, **kw: '\n'.join(paths), run=run)

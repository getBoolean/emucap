import tempfile
import unittest
from pathlib import Path
from unittest import mock

from build import compiler_target, patch_digest


class BuildRecipeTests(unittest.TestCase):
    def test_patch_digest_binds_names_and_content_in_stable_order(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'a.patch', Path(directory) / 'b.patch'
            first.write_bytes(b'one')
            second.write_bytes(b'two')
            original = patch_digest([first, second])
            self.assertEqual(original, patch_digest([second, first]))
            first.write_bytes(b'changed')
            self.assertNotEqual(original, patch_digest([first, second]))
            first.write_bytes(b'one')
            renamed = first.rename(first.with_name('renamed.patch'))
            self.assertNotEqual(original, patch_digest([renamed, second]))

    def test_profile_target_records_native_compiler_abi(self):
        for machine, target in (
            ('x86_64-w64-mingw32', 'x86_64-pc-windows-gnu'),
            ('x86_64-linux-gnu', 'x86_64-unknown-linux-gnu'),
            ('aarch64-linux-musl', 'aarch64-unknown-linux-musl'),
            ('arm64-apple-darwin24.0.0', 'aarch64-apple-darwin'),
        ):
            with mock.patch('build.run', return_value=machine):
                self.assertEqual(compiler_target('compiler'), target)
        with mock.patch('build.run', return_value='i686-w64-mingw32'):
            with self.assertRaisesRegex(RuntimeError, 'Unqualified architecture'):
                compiler_target('compiler')

"""Build preparation preserves edited source and binds the emitted native identity."""
import importlib.util
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

ADAPTER = pathlib.Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('eden_build', ADAPTER / 'build.py')
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class PrepareTests(unittest.TestCase):
    def test_runtime_dlls_follow_selected_compiler_instead_of_path_or_working_directory(self):
        with tempfile.TemporaryDirectory(prefix='emucap-eden-runtime-') as directory:
            root = pathlib.Path(directory).resolve()
            build, destination = root / 'build', root / 'bin'
            selected, older = root / 'selected', root / 'older'
            for path in (build, destination, selected, older):
                path.mkdir()
            compiler = selected / 'g++.exe'
            compiler.write_bytes(b'compiler fixture')
            (build / 'CMakeCache.txt').write_text(
                'CMAKE_CXX_COMPILER:FILEPATH=' + compiler.as_posix() + '\n', encoding='utf-8')
            (selected / 'libstdc++-6.dll').write_bytes(b'selected absolute runtime')
            (selected / 'libgcc_s_seh-1.dll').write_bytes(b'selected adjacent runtime')
            (older / 'libstdc++-6.dll').write_bytes(b'older PATH runtime')
            (root / 'libgcc_s_seh-1.dll').write_bytes(b'unrelated working directory runtime')

            def query(actual_compiler, argument):
                self.assertEqual(actual_compiler, compiler)
                name = argument.removeprefix('-print-file-name=')
                return str(selected / name) if name == 'libstdc++-6.dll' else name

            previous = pathlib.Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.dict(os.environ, {'PATH': str(older)}), mock.patch.object(BUILD, 'output', query):
                    BUILD.copy_windows_runtime(build, destination)
            finally:
                os.chdir(previous)
            self.assertEqual((destination / 'libstdc++-6.dll').read_bytes(), b'selected absolute runtime')
            self.assertEqual((destination / 'libgcc_s_seh-1.dll').read_bytes(), b'selected adjacent runtime')
            self.assertEqual(sorted(path.name for path in destination.iterdir()),
                             ['libgcc_s_seh-1.dll', 'libstdc++-6.dll'])

    def test_runtime_copy_requires_recorded_compiler(self):
        with tempfile.TemporaryDirectory(prefix='emucap-eden-cache-') as directory:
            root = pathlib.Path(directory)
            (root / 'CMakeCache.txt').write_text('CMAKE_BUILD_TYPE:STRING=Release\n', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'selected C\\+\\+ compiler'):
                BUILD.copy_windows_runtime(root, root)

    def test_required_cpu_features_match_upstream_platform_flags(self):
        self.assertEqual(BUILD.cpu_features_for('x86_64-pc-windows-gnu'), ['cmpxchg16b', 'sse4.1'])
        self.assertEqual(BUILD.cpu_features_for('x86_64-unknown-linux-gnu'), ['cmpxchg16b'])
        self.assertEqual(BUILD.cpu_features_for('aarch64-apple-darwin'), [])

    def test_repeated_prepare_and_edited_source_rejection(self):
        with tempfile.TemporaryDirectory(prefix='emucap-eden-prepare-') as directory:
            root = pathlib.Path(directory)
            source, destination = root / 'source', root / 'bin'
            source.mkdir()
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            fixture = source / 'fixture.txt'
            fixture.write_bytes(b'one\n')
            subprocess.run(['git', 'add', 'fixture.txt'], cwd=source, check=True)
            subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid',
                            'commit', '-qm', 'Fixture'], cwd=source, check=True)
            revision = BUILD.output('git', 'rev-parse', 'HEAD', cwd=source)
            patch = root / 'integration.patch'
            patch.write_bytes(b'--- a/fixture.txt\n+++ b/fixture.txt\n@@ -1 +1 @@\n-one\n+two\n')
            profile = {'fork': 'custom-fixture', 'repository': 'https://example.invalid/fork.git',
                       'revision': revision, 'systems': ['switch'], 'renderers': ['vulkan']}
            unrelated = source / 'user-untracked.txt'
            unrelated.write_text('preserve this')
            emitted = BUILD.prepare(profile, source, destination, 'x86_64-unknown-linux-gnu', ['vulkan'], patch)
            BUILD.prepare(profile, source, destination, 'x86_64-unknown-linux-gnu', ['vulkan'], patch)
            self.assertEqual(fixture.read_text(), 'two\n')
            self.assertEqual(unrelated.read_text(), 'preserve this')
            self.assertEqual(json.loads((destination / 'emucap-emulator-build.pending.json').read_text()), emitted)
            self.assertFalse((destination / 'emucap-emulator-build.json').exists())
            header = (source / 'src/yuzu_cmd/emucap/EmucapBuildProfile.h').read_text()
            self.assertIn(emitted['patch_sha256'], header)
            fixture.write_text('two\nuser edit\n')
            with self.assertRaises((RuntimeError, subprocess.CalledProcessError)):
                BUILD.prepare(profile, source, destination, 'x86_64-unknown-linux-gnu', ['vulkan'], patch)
            self.assertEqual(fixture.read_text(), 'two\nuser edit\n')
            self.assertEqual(unrelated.read_text(), 'preserve this')


if __name__ == '__main__':
    unittest.main()

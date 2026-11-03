"""Fork native archives retain verifiable runtime contents on both hosts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('pico_native', HERE / 'pico_native.py')
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class NativeArchiveTests(unittest.TestCase):
    def test_checksum_uses_portable_ascii_lf_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'runtime.zip'
            path.write_bytes(b'payload')
            package.checksum(path)
            self.assertEqual(path.with_name(path.name + '.sha256').read_bytes(),
                             b'239f59ed55e737c77147cf55ad0c1b030b6d7ee748a7426952f9b852d5a935e5  runtime.zip\n')

    def test_linux_libraries_retain_their_package_notices(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage, notices, docs, common = (root / name for name in ('runtime', 'notices', 'docs', 'common'))
            (stage / 'lib').mkdir(parents=True)
            (stage / 'lib/libexample.so.1').write_bytes(b'library')
            (docs / 'libexample1').mkdir(parents=True)
            (docs / 'libexample1/copyright').write_text('Example copyright and license')
            common.mkdir()
            (common / 'LGPL-2.1').write_text('Common full license text')
            with patch.object(package, 'run', return_value='libexample1:amd64: /usr/lib/libexample.so.1'):
                package.linux_notices(stage, notices, docs, common)
            self.assertEqual((notices / 'dependencies/libexample1/copyright').read_text(),
                             'Example copyright and license')
            self.assertEqual((notices / 'common-licenses/LGPL-2.1').read_text(), 'Common full license text')

    def test_extracted_smoke_requires_expected_options_and_process_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            manifest = {'executable': 'desmume-cli'}
            for code, output in [(1, 'missing library'), (127, '--arm9gdb --cflash-image')]:
                with self.subTest(code=code, output=output), patch.object(package.subprocess, 'run',
                        return_value=SimpleNamespace(returncode=code, stdout=output, stderr='')):
                    with self.assertRaisesRegex(ValueError, 'startup'):
                        package.runtime_smoke(stage, manifest)
            with patch.object(package.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=1, stdout='--arm9gdb --cflash-image', stderr='')):
                package.runtime_smoke(stage, manifest)

    def test_both_archive_formats_preserve_manifest_dlls_and_licenses(self):
        for platform in ('windows', 'linux'):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                name = 'emucap-1.1.0-pico.2-desmume-nds-test'
                stage = root / name
                stage.mkdir()
                binary = stage / ('desmume-cli.exe' if platform == 'windows' else 'desmume-cli')
                binary.write_bytes(b'native executable')
                (stage / 'dependency.dll').write_bytes(b'required dependency')
                (stage / 'licenses').mkdir()
                (stage / 'licenses/COPYING').write_text('license')
                manifest = package.runtime_manifest(stage, binary.name, '1.1.0-pico.2',
                                                    'a' * 40, 'b' * 40, 'c' * 64)
                self.assertEqual(manifest['version'], '1.1.0-pico.2')
                self.assertEqual(manifest['source_revision'], 'a' * 40)
                self.assertEqual(manifest['upstream_revision'], 'b' * 40)
                self.assertEqual(manifest['patchset_sha256'], 'c' * 64)
                self.assertEqual(set(manifest['files']),
                                 {binary.name, 'dependency.dll', 'licenses/COPYING'})
                (stage / 'NATIVE-PACKAGE.json').write_text(json.dumps(manifest))
                archive = package.archive_runtime(stage, root / 'artifacts', platform)
                package.verify_archive(archive, name)
                self.assertTrue(archive.with_name(archive.name + '.sha256').is_file())

    def test_modified_runtime_member_fails_extracted_manifest_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / 'runtime'
            stage.mkdir()
            (stage / 'desmume-cli.exe').write_bytes(b'expected')
            manifest = package.runtime_manifest(stage, 'desmume-cli.exe', '1.1.0-pico.2',
                                                'a' * 40, 'b' * 40, 'c' * 64)
            (stage / 'NATIVE-PACKAGE.json').write_text(json.dumps(manifest))
            (stage / 'desmume-cli.exe').write_bytes(b'corrupt')
            archive = root / 'tampered.zip'
            with zipfile.ZipFile(archive, 'w') as packed:
                for path in stage.rglob('*'):
                    packed.write(path, 'runtime/' + path.relative_to(stage).as_posix())
            with self.assertRaisesRegex(ValueError, 'manifest mismatch'):
                package.verify_archive(archive, 'runtime')


if __name__ == '__main__':
    unittest.main()

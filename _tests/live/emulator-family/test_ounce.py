import importlib.util
from pathlib import Path
import unittest
import struct
import tempfile
import hashlib
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('ounce_npdm', Path(__file__).with_name('ounce_npdm.py'))
OUNCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OUNCE)
BUILD_SPEC = importlib.util.spec_from_file_location('build_ounce_fixture', Path(__file__).with_name('build_ounce_fixture.py'))
BUILD = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(BUILD)


class OunceMetadataTests(unittest.TestCase):
    def test_library_bytes_must_match_expected_build(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            library = source / 'nx/lib/libnx.a'
            library.parent.mkdir(parents=True)
            library.write_bytes(b'qualified library')
            digest = hashlib.sha256(library.read_bytes()).hexdigest()
            with patch.object(BUILD.subprocess, 'check_output', side_effect=[BUILD.LIBOUNCE_REVISION, b'', b'']):
                self.assertEqual(BUILD.checked_library(source, digest), digest)
            library.write_bytes(b'stale archive from another build')
            with patch.object(BUILD.subprocess, 'check_output', side_effect=[BUILD.LIBOUNCE_REVISION, b'', b'']):
                with self.assertRaisesRegex(ValueError, 'archive differs'):
                    BUILD.checked_library(source, digest)

    def test_untracked_library_sources_are_rejected(self):
        with patch.object(BUILD.subprocess, 'check_output', side_effect=[BUILD.LIBOUNCE_REVISION, b'', b'nx/include/shadow.h\n']):
            with self.assertRaisesRegex(ValueError, 'untracked nx'):
                BUILD.checked_library(Path('unused'), '0' * 64)

    def fixture(self):
        data = bytearray(0x500)
        data[:4] = b'META'
        struct.pack_into('<4I', data, 0x70, 0x400, 0x100, 0x80, 0x380)
        data[0x380:0x384] = b'ACID'
        struct.pack_into('<I', data, 0x384, 0x200)
        struct.pack_into('<2Q', data, 0x390, 0x040000000001E001, 0x040000000001E001)
        struct.pack_into('<6I', data, 0x3a0, 0x340, 0x10, 0x350, 0x10, 0x360, 0x20)
        data[0x400:0x404] = b'ACI0'
        struct.pack_into('<Q', data, 0x410, 0x040000000001E001)
        struct.pack_into('<6I', data, 0x420, 0x40, 0x10, 0x50, 0x10, 0x60, 0x20)
        return data

    def test_valid_layout_and_corrupt_sections(self):
        valid = self.fixture()
        self.assertEqual(OUNCE.validate(valid)['program_id'], '040000000001e001')
        for offset, value in [(0x78, 0x400), (0x3a0, 0xfffffff0),
                              (0x3a8, 0x340), (0x384, 0), (0x410, 1)]:
            with self.subTest(offset=offset):
                bad = valid.copy()
                struct.pack_into('<I', bad, offset, value)
                with self.assertRaises(ValueError):
                    OUNCE.validate(bad)

    def test_nx_magic_does_not_establish_ounce(self):
        data = self.fixture()
        data[0x280:0x284] = b'ACID'
        data[0x380:0x384] = b'\0' * 4
        with self.assertRaisesRegex(ValueError, 'Ounce ACID'):
            OUNCE.validate(data)

    def test_truncated_header_is_rejected(self):
        with self.assertRaises(ValueError):
            OUNCE.validate(b'META')

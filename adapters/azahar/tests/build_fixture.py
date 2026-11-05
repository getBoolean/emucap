"""Build the executable ABI fixture; absence of a C compiler is a test failure."""
import os
import pathlib
import shutil
import subprocess
import sys
import json

PROFILE = {'schema': 'emucap-emulator-build/v1', 'family': 'azahar-libretro', 'fork': 'azahar',
           'repository': 'https://github.com/azahar-emu/azahar.git',
           'revision': '9c38437daad90a2f05f55a047d04d4073a476456', 'patch_sha256': '0' * 64,
           'bridge_api': 1, 'systems': ['3ds'], 'renderers': ['software'],
           'cpu_features': [], 'target': 'test-host'}


def build_fixture(destination):
    compiler = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    if not compiler:
        raise RuntimeError('A C compiler (CC, gcc or clang) is required for libretro ABI tests')
    destination = pathlib.Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    profile = json.dumps(PROFILE, separators=(',', ':'))
    (destination / 'emucap-emulator-build.json').write_text(profile)
    (destination / 'emucap_profile.h').write_text('#define EMUCAP_BUILD_PROFILE_JSON ' + json.dumps(profile))
    library = destination / ('fake_core.dll' if sys.platform == 'win32' else 'fake_core.so')
    subprocess.run([compiler, '-shared', '-fPIC', '-O0', str(pathlib.Path(__file__).with_name('fake_core.c')),
                    '-I', str(destination), '-o', str(library)], check=True, capture_output=True, text=True)
    return library

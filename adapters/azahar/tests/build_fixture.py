"""Build the executable ABI fixture; absence of a C compiler is a test failure."""
import os
import pathlib
import shutil
import subprocess
import sys


def build_fixture(destination):
    compiler = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    if not compiler:
        raise RuntimeError('A C compiler (CC, gcc or clang) is required for libretro ABI tests')
    destination = pathlib.Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    library = destination / ('fake_core.dll' if sys.platform == 'win32' else 'fake_core.so')
    subprocess.run([compiler, '-shared', '-fPIC', '-O0', str(pathlib.Path(__file__).with_name('fake_core.c')),
                    '-o', str(library)], check=True, capture_output=True, text=True)
    return library

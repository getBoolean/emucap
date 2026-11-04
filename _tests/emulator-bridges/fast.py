#!/usr/bin/env python3
"""Required synthetic native proof, kept separate from emulator/guest qualification."""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--cc', default=os.environ.get('CC', 'gcc'))
    parser.add_argument('--cxx', default=os.environ.get('CXX', 'g++'))
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    result = {'proof_level': 'synthetic-native-abi-and-protocol', 'live_qualified': False,
              'host': platform.platform(), 'python': sys.version, 'checks': [], 'status': 'failed'}

    def check(name, command, env=None):
        with (evidence / (name + '.log')).open('w', encoding='utf-8') as log:
            process = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                     stderr=subprocess.STDOUT, timeout=600)
        result['checks'].append({'name': name, 'exit_code': process.returncode})
        process.check_returncode()

    try:
        if sys.version_info < (3, 12):
            raise RuntimeError('A real Python 3.12+ executable is required')
        # Compile and load before unittest discovery. A missing ABI fixture is never a skip.
        spec = importlib.util.spec_from_file_location(
            'build_fixture', ROOT / 'adapters/azahar/tests/build_fixture.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        os.environ['CC'] = args.cc
        with tempfile.TemporaryDirectory(prefix='emucap-abi-ci-') as temporary:
            library = module.build_fixture(temporary)
            native = ctypes.CDLL(str(library))
            native.retro_api_version.restype = ctypes.c_uint
            if native.retro_api_version() != 1:
                raise RuntimeError('Synthetic libretro fixture has the wrong ABI')
            result['fixture'] = {'sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
                                 'loaded': True, 'retro_api_version': 1}
            # Windows keeps loaded DLLs open until process exit.
            if os.name == 'nt':
                import _ctypes
                _ctypes.FreeLibrary(native._handle)
            del native
        check('azahar-worker', [sys.executable, '-m', 'unittest', 'discover',
                               '-s', 'adapters/azahar', '-p', 'test_*.py'])
        check('eden-build-profile', [sys.executable, '-m', 'unittest', 'discover',
                                    '-s', 'adapters/eden-family/tests', '-p', 'test_*.py'])
        check('guest-pixel-admission', [sys.executable, '-m', 'unittest', 'discover',
                                      '-s', '_tests/live/emulator-family', '-p', 'test_*.py'])
        check('core-package-boundaries', [sys.executable, '_tests/release/package_core_tests.py'])
        check('live-artifact-admission', [sys.executable, '-m', 'unittest', 'discover',
                                           '-s', '_tests/emulator-bridges', '-p', 'test_*.py'])
        check('eden-native-endpoint', [sys.executable, 'adapters/eden-family/tests/run.py',
                                       '--cxx', args.cxx])
        result['status'] = 'passed'
    except Exception as error:
        result['error'] = str(error)
        if getattr(error, 'stderr', None):
            result['compiler_diagnostics'] = error.stderr
        raise
    finally:
        (evidence / 'fast-results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

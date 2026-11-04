#!/usr/bin/env python3
"""Run a pinned source build; persist failure evidence without claiming live qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fork', choices=('azahar', 'eden', 'eden-nx2', 'eglantine'), required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    payload = evidence / 'payload'
    if args.fork == 'azahar':
        command = [sys.executable, '-u', str(ROOT / 'adapters/azahar/build.py'),
                   '--source-dir', str(ROOT / 'adapters/azahar/work/source'),
                   '--build-dir', str(ROOT / 'adapters/azahar/work/cmake'),
                   '--output-dir', str(payload), '--jobs', str(args.jobs)]
    else:
        command = [sys.executable, '-u', str(ROOT / 'adapters/eden-family/build.py'),
                   '--fork', args.fork, '--output', str(payload), '--jobs', str(args.jobs)]
    result = {'proof_level': 'native-source-build', 'live_qualified': False, 'fork': args.fork,
              'host': platform.platform(), 'python': sys.version, 'command': command,
              'status': 'failed'}
    try:
        with (evidence / 'native-build.log').open('w', encoding='utf-8') as log:
            process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=3 * 60 * 60)
        result['exit_code'] = process.returncode
        process.check_returncode()
        profile = json.loads((payload / 'emucap-emulator-build.json').read_text(encoding='utf-8'))
        if profile['fork'] != args.fork:
            raise RuntimeError('Output profile differs from the requested fork build')
        binaries = [path for path in payload.iterdir()
                    if path.is_file() and (path.suffix in ('.dll', '.so', '.dylib')
                                           if args.fork == 'azahar' else path.name in ('eden-sdl', 'eden-sdl.exe'))]
        if not binaries:
            raise RuntimeError('Native recipe produced no emulator binary')
        result['build_profile'] = profile
        result['binaries'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in binaries}
        result['status'] = 'passed'
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        (evidence / 'native-build-results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

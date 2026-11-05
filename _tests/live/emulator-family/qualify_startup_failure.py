"""Verify a real Eden-family failed startup exits cleanly under GDB's Windows debug heap."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('binary', 'gdb', 'content', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--system', choices=['switch', 'switch2'], required=True)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('this regression requires Windows and GDB with the default debug heap')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    home = out / 'user'
    home.mkdir()
    config = home / 'config.ini'
    config.write_text(('[Core]\nmemory_layout_mode=4\nmemory_layout_mode\\default=false\n'
                       if args.system == 'switch2' else '') +
                      '[Renderer]\nvulkan_device=999\nvulkan_device\\default=false\n', encoding='utf-8')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('EMUCAP_') and key != '_NO_DEBUG_HEAP'}
    env.update(EMUCAP_USER_ROOT=str(home), EMUCAP_DISPLAY='0')
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    result = {'status': 'failed', 'system': args.system,
              'claims': 'real native failed-start teardown only; no guest control credit'}
    process = None
    try:
        binary = args.binary.resolve()
        result['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
        result['content_sha256'] = hashlib.sha256(args.content.read_bytes()).hexdigest()
        command = [str(args.gdb.resolve()), '-batch', '-ex', 'set pagination off',
                   '-ex', 'set confirm off', '-ex', 'run',
                   '-ex', 'printf "EMUCAP_INFERIOR_EXIT=%d\\n", $_exitcode',
                   '-ex', 'thread apply all bt 12', '--args', str(binary),
                   '--config', str(config), str(args.content.resolve())]
        with (out / 'gdb.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                result['gdb_exit_code'] = process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=log, stderr=log, check=True, timeout=10)
                process.wait(timeout=10)
                raise RuntimeError('native failed-start teardown exceeded 60 seconds')
        diagnostic = (out / 'gdb.log').read_text(encoding='utf-8', errors='replace')
        native = (home / 'log/eden_log.txt').read_text(encoding='utf-8', errors='replace')
        if 'Invalid device index 999' not in native:
            raise RuntimeError('did not reach the intended invalid-device startup failure')
        if result['gdb_exit_code'] != 0 or 'EMUCAP_INFERIOR_EXIT=1\n' not in diagnostic:
            raise RuntimeError('native failed startup did not exit cleanly with status 1')
        if 'received signal' in diagnostic:
            raise RuntimeError('native failed startup raised a debugger-visible fault')
        result['status'] = 'passed'
    except Exception as error:
        result['error'] = str(error)
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Live Dolphin input checks using original Input Lab GameCube/Wii guests.

Only the public emucap controller surface is used. No dormant native analog
handler, keyboard injection, commercial content, firmware or keys are used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time

from observation import decode, require_state

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '_tests/live/mesen2'))
from support import McpProcess
sys.path.insert(0, str(ROOT / '_tests/live/emulator-family'))
from qualify import collect_runtime_evidence, remove_runtime_home

MAPPING = {
    'gamecube': {'a': 0, 'b': 1, 'x': 2, 'y': 3, 'l': 4, 'r': 5, 'z': 7,
                 'start': 9, 'up': 12, 'down': 13, 'left': 14, 'right': 15},
    'wii': {'a': 0, 'b': 1, 'one': 2, 'two': 3, 'minus': 8, 'plus': 9,
            'up': 12, 'down': 13, 'left': 14, 'right': 15, 'home': 18},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mcp', required=True, type=Path)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--fixture', required=True, type=Path, help='Native builder output directory')
    parser.add_argument('--system', choices=['gamecube', 'wii'], required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--display', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.fixture / 'fixture.json').read_text(encoding='utf-8'))
    content = (args.fixture / manifest['content']).resolve(strict=True)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    if manifest['system'] != args.system or sha(content) != manifest['content_sha256']:
        raise RuntimeError('fixture identity differs from manifest')
    result = {'status': 'failed', 'system': args.system, 'passed': [],
              'rejected_unsupported_requests': [],
              'build_id': manifest['build_id'], 'display': args.display,
              'proof': 'guest pixel observations through public MCP',
              'sha256': {'content': sha(content), 'mcp': sha(args.mcp), 'binary': sha(args.binary),
                         'sidecar': sha(args.binary.parent / 'emucap-dolphin-build.json')},
              'unsupported': ['nonzero injection ports', 'public MCP analog/trigger injection',
                              'Wii IR/extensions' if args.system == 'wii' else 'analog A/B pressure']}
    mcp, launch_id = None, None
    with tempfile.TemporaryDirectory(prefix='emucap-input-lab-dolphin-', delete=False) as home:
        try:
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            env = dict(os.environ, EMUCAP_REPO_ROOT=str(ROOT), EMUCAP_EMU_HOME=home,
                       EMUCAP_BROKER='0', EMUCAP_PORT=str(port),
                       EMUCAP_DOLPHIN_HEADLESS_BIN=str(args.binary.resolve()))
            env['EMUCAP_DOLPHIN_GUI_BIN'] = str(args.binary.resolve())
            mcp = McpProcess(args.mcp.resolve(), env, out / 'mcp.log')
            mcp.initialize()
            selection = {'system': args.system, 'content_path': str(content)}
            plan = mcp.tool('launch_plan', selection)
            (out / 'launch-plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
            if not plan.get('ready_to_launch'):
                raise RuntimeError(f'launch blocked: {plan.get("next_action")}')
            launched = mcp.tool('launch', dict(selection, display=args.display, sound=False))
            if not launched.get('launched'):
                raise RuntimeError(f'launch rejected: {launched}')
            launch_id = launched['runtime_instance']['launch_id']
            status = mcp.tool('status', {})
            (out / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
            if status.get('contracts', {}).get('state') != 'validated' or 'set_input' not in status['methods']:
                raise RuntimeError('validated controller contract unavailable')
            if status.get('state') != 'running':
                mcp.tool('resume', {})

            def debug(buttons):
                current = mcp.tool('status', {})
                return mcp.tool('debug', {'operation': 'set_input',
                    'arguments': {'port': 0, 'buttons': buttons},
                    'known_capability_revision': current['capability_revision']})

            def expect_rejected(label, arguments):
                current = mcp.tool('status', {})
                response = mcp.request('tools/call', {'name': 'debug', 'arguments': {
                    'operation': 'set_input', 'arguments': arguments,
                    'known_capability_revision': current['capability_revision']}})
                (out / (label + '.json')).write_text(json.dumps(response, indent=2), encoding='utf-8')
                if not response.get('error') and not response.get('result', {}).get('isError'):
                    raise AssertionError(f'unsupported input was accepted: {label}')
                result['rejected_unsupported_requests'].append(label)

            sequences = [0] * 4
            target = 6 if args.system == 'gamecube' else 7
            def snapshot(label, buttons):
                from PIL import Image
                deadline = time.monotonic() + 30
                path = out / (label + '.png')
                while True:
                    try:
                        mcp.tool('screenshot', {'save_path': str(path)}, timeout=40)
                        observations = []
                        with Image.open(path) as full:
                            if full.size != (640, 480):
                                raise ValueError(f'expected native 640x480 capture, got {full.size}')
                            for port in range(4):
                                crop = out / (label + f'-port{port}.png')
                                x, y = port % 2 * 320, port // 2 * 240
                                full.crop((x, y, x + 320, y + 240)).save(crop)
                                observed = decode(crop, 320, 240, target=target, build_id=manifest['build_id'])
                                if observed['port'] != port:
                                    raise AssertionError('wrong guest port identity')
                                delta = (observed['sequence'] - sequences[port]) & 0xffffffff
                                if not 0 < delta < 0x80000000:
                                    raise AssertionError(f'stale guest sample on port {port}')
                                if port == 0:
                                    require_state(observed, {'port': 0, 'buttons': buttons,
                                        'axes': [0] * 4, 'triggers': [0, 0], 'touch': None},
                                        after=sequences[port])
                                else:
                                    if observed['buttons'] or any(observed['axes']) or any(observed['triggers']):
                                        raise AssertionError(f'input leaked to port {port}: {observed}')
                                observations.append(observed)
                        if len({item['sequence'] for item in observations}) != 1:
                            raise AssertionError('four port panels are not from one guest sample')
                        break
                    except (ValueError, AssertionError, RuntimeError) as error:
                        result.setdefault('capture_attempts', []).append({'label': label, 'error': str(error)})
                        if time.monotonic() >= deadline:
                            for name, arguments in [('status', {}), ('get_state', {'groups': ['cpu']})]:
                                try:
                                    result['failed_' + name] = mcp.tool(name, arguments)
                                except Exception as diagnostic_error:
                                    result['failed_' + name] = str(diagnostic_error)
                            raise RuntimeError(f'{label}: {error}') from error
                        time.sleep(0.1)
                for port, observed in enumerate(observations):
                    sequences[port] = observed['sequence']
                (out / (label + '.json')).write_text(json.dumps(observations, indent=2), encoding='utf-8')
                result['passed'].append(label)

            debug([])
            snapshot('neutral', 0)
            expect_rejected('port-one-rejected', {'port': 1, 'buttons': ['a']})
            expect_rejected('analog-rejected', {'port': 0, 'buttons': ['a'], 'axes': {'stickX': 200}})
            snapshot('rejected-input-preserved-neutral', 0)
            snapshot('progress', 0)
            for button, bit in MAPPING[args.system].items():
                debug([button])
                snapshot(button + '-hold', 1 << bit)
                snapshot(button + '-sustained', 1 << bit)
                debug([])
                snapshot(button + '-release', 0)
            combo = ['a', 'b', 'up', 'right']
            debug(combo)
            snapshot('combined', sum(1 << MAPPING[args.system][name] for name in combo))
            debug([])
            snapshot('final-release', 0)
            result['status'] = 'passed'
        except Exception as error:
            result['error'] = str(error)
            raise
        finally:
            errors = []
            if mcp:
                try:
                    if launch_id:
                        stopped = mcp.tool('stop', {'launch_id': launch_id})
                        result['stop'] = stopped
                        if not stopped.get('stopped') or stopped.get('status') != 'completed':
                            raise RuntimeError('managed stop incomplete')
                except Exception as error:
                    errors.append(str(error))
                finally:
                    try:
                        mcp.close()
                    except Exception as error:
                        errors.append(str(error))
            try:
                collect_runtime_evidence(Path(home), out)
                for log in Path(home).rglob('*.log'):
                    target_log = out / 'runtime-logs' / log.relative_to(home)
                    target_log.parent.mkdir(parents=True, exist_ok=True)
                    with log.open('rb') as source:
                        target_log.write_bytes(source.read(16 * 1024 * 1024))
                if not errors and result['status'] == 'passed':
                    remove_runtime_home(Path(home))
                else:
                    result['preserved_runtime_home'] = home
            except Exception as error:
                errors.append(str(error))
            if errors:
                result['status'] = 'failed'
                result['cleanup_error'] = '; '.join(errors)
                result['preserved_runtime_home'] = home
            (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    if result['status'] != 'passed':
        raise RuntimeError(result.get('cleanup_error', 'qualification failed'))
    print(json.dumps({'status': result['status'], 'observations': len(result['passed'])}))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Opt-in managed-launch qualification; absence of native/guest proof fails closed.

Requires Pillow. Inputs must be lawful fixtures using the EMUC pixel witness format.
The libnx fixture proves Switch 1 behavior only, even when run by a Switch 2 fork.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '_tests/live/mesen2'))
from support import McpProcess


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def collect_runtime_evidence(home, output):
    def redact(value):
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()
                    if not any(word in key.lower() for word in ('token', 'secret', 'credential'))
                    and not key.lower().endswith('_key')}
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value
    for name in ('azahar-startup.json', 'termination.json', 'link.json'):
        for path in home.glob('sessions/*/generations/*/' + name):
            if path.stat().st_size > 4 * 1024 * 1024:
                raise RuntimeError('runtime evidence record exceeds bound')
            value = redact(json.loads(path.read_text(encoding='utf-8')))
            (output / ('runtime-' + name)).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    for path in home.glob('sessions/*/generations/*/emulator.log'):
        with path.open('rb') as source:
            (output / 'native.log').write_bytes(source.read(16 * 1024 * 1024))


def decode(path, system):
    from PIL import Image
    with Image.open(path) as image:
        image = image.convert('RGB')
        native_width = 400 if system == '3ds' else 1280
        scale = image.width / native_width
        if scale <= 0 or image.height != (480 if system == '3ds' else 720) * scale:
            raise RuntimeError(f'capture dimensions do not contain witness: {image.size}')
        values = []
        for y in (16, 40, 64, 88, 112, 136):
            value = 0
            for bit in range(32):
                rgb = image.getpixel((int((20 + bit * 8) * scale), int((y + 4) * scale)))
                if min(rgb) > 192:
                    value |= 1 << bit
                elif max(rgb) > 64:
                    raise RuntimeError(f'pixel is not a witness bit: {rgb}')
            values.append(value)
        if values[0] != 0x454d5543:
            raise RuntimeError(f'guest magic missing: {values}')
        identity = {'3ds': 3, 'switch': 1, 'switch2': 2}[system]
        if values[5] != identity:
            raise RuntimeError(f'guest target identity mismatch: expected {identity}, got {values[5]}')
        result = dict(zip(('magic', 'frame', 'buttons', 'stick', 'touch', 'system'), values))
        if system == '3ds':
            result['bottom_level'] = image.getpixel((int(200 * scale), int(360 * scale)))[0]
        return result


def require_touch(status, system):
    bounds = status.get('touch_capability')
    width, height = (320, 240) if system == '3ds' else (1280, 720)
    if (not isinstance(bounds, dict) or bounds.get('ports') != [0]
            or bounds.get('width') != width or bounds.get('height') != height
            or bounds.get('contacts') != 1 or bounds.get('coordinate_space') != 'touchscreen'
            or not {'hold_touch', 'release_touch'} <= set(status.get('methods', []))):
        raise RuntimeError('expected maintained-family touchscreen capability is absent or incompatible')
    return bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('mcp', 'binary', 'content', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    for name in ('core', 'python', 'profile', 'config'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--fork', required=True, choices=['azahar', 'eden', 'eden-nx2', 'eglantine'])
    parser.add_argument('--system', required=True, choices=['3ds', 'switch', 'switch2'])
    parser.add_argument('--renderer', choices=['software', 'opengl', 'vulkan'])
    parser.add_argument('--display', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    evidence = {'status': 'blocked', 'fork': args.fork, 'system': args.system,
                'checks': {}, 'claims': 'exact fixture/config only; no deterministic stepping claim'}
    mcp = None
    launch_id = None
    runtime_home = None
    try:
        for key in ('mcp', 'binary', 'content'):
            path = getattr(args, key).resolve()
            if not path.is_file():
                raise RuntimeError(f'missing {key}: {path}')
            evidence[key + '_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        # Import before launch so missing validation dependencies cannot strand a generation.
        from PIL import Image
        options = {'fork': args.fork, 'binary': str(args.binary.resolve())}
        for key in ('core', 'python', 'profile', 'config'):
            value = getattr(args, key)
            if value:
                options[key] = str(value.resolve())
        if args.renderer:
            options['renderer'] = args.renderer
        runtime_home = Path(tempfile.mkdtemp(prefix='emucap-live-home-'))
        env = dict(os.environ, EMUCAP_REPO_ROOT=str(ROOT), EMUCAP_BROKER='0',
                   EMUCAP_PORT=str(free_port()), EMUCAP_EMU_HOME=str(runtime_home))
        mcp = McpProcess(args.mcp.resolve(), env, out / 'mcp.log')
        mcp.initialize()

        def call(name, arguments=None):
            value = mcp.tool(name, arguments or {}, timeout=90)
            # Persist diagnostics, never credentials or screenshot base64.
            (out / f'{len(evidence["checks"]):03}-{name}.json').write_text(
                json.dumps(value, indent=2) + '\n', encoding='utf-8')
            evidence['checks'][str(len(evidence['checks']))] = name
            return value

        selection = {'system': args.system, 'content_path': str(args.content.resolve()),
                     'emulator': options, 'display': args.display}
        plan_selection = {key: value for key, value in selection.items() if key != 'display'}
        plan = call('launch_plan', plan_selection)
        if plan.get('indirect_media', {}).get('state') == 'review_required':
            raise RuntimeError('composite fixture requires explicit reviewed-media approval; use documented launch_plan flow')
        launched = call('launch', selection)
        if not launched.get('launched'):
            raise RuntimeError(f'managed launch rejected: {launched}')
        evidence['status'] = 'failed'
        launch_id = launched.get('runtime_instance', {}).get('launch_id')
        status = call('status')
        launch_id = status['runtime_instance']['launch_id']
        if status.get('contracts', {}).get('state') != 'validated':
            raise RuntimeError('runtime capability contracts are not validated')
        touch_bounds = require_touch(status, args.system)
        mismatched_profile = json.loads(json.dumps(status['host_build']))
        mismatched_profile['patch_sha256'] = 'ff' * 32
        bad_profile_path = out / 'mismatched-build-profile.json'
        bad_profile_path.write_text(json.dumps(mismatched_profile), encoding='utf-8')
        rejected_selection = dict(selection, replace=True,
            emulator=dict(options, profile=str(bad_profile_path)))
        rejected_wire = mcp.request('tools/call', {'name': 'launch', 'arguments': rejected_selection})
        rejected = rejected_wire.get('result', {}).get('structuredContent', {})
        if rejected.get('launched') is not False or 'compiled emulator profile differs' not in rejected.get('error', ''):
            raise RuntimeError(f'mismatched compiled profile did not fail at preflight: {rejected_wire}')
        after_rejection = call('status')
        if after_rejection.get('runtime_instance', {}).get('launch_id') != launch_id or not after_rejection.get('connected'):
            raise RuntimeError('failed replacement disturbed the existing guest generation')
        evidence['failed_replacement_preserved_generation'] = True
        if status.get('state') != 'running':
            call('resume')

        def debug(operation, arguments):
            current = call('status')
            return call('debug', {'operation': operation, 'arguments': arguments,
                                 'known_capability_revision': current['capability_revision']})

        def snapshot(label):
            deadline = time.monotonic() + 30
            while True:
                terminal = debug('wait_for_running_frames', {'frames': 3, 'timeout_ms': 10000})
                if terminal.get('status') != 'completed':
                    raise RuntimeError(f'native progress wait did not complete: {terminal}')
                path = out / (label + '.png')
                # Screenshot is an image result; tool() expects structured content too.
                call('screenshot', {'save_path': str(path)})
                try:
                    return decode(path, args.system)
                except RuntimeError:
                    if time.monotonic() >= deadline:
                        raise

        first = snapshot('initial')
        second = snapshot('advancing')
        if second['frame'] <= first['frame']:
            raise RuntimeError('render progress did not advance guest-visible counter')
        debug('set_input', {'port': 0, 'buttons': ['a'], 'axes': {'stick_x': 24000}})
        held = snapshot('held')
        if held['buttons'] != 1 or not 0 < (held['stick'] & 0xffff) < 32768:
            raise RuntimeError(f'guest did not consume button/stick: {held}')
        current = call('status')
        request_id = mcp.next_id
        mcp.next_id += 1
        pending = {'jsonrpc': '2.0', 'id': request_id, 'method': 'tools/call', 'params': {
            'name': 'debug', 'arguments': {'operation': 'wait_for_running_frames',
                'arguments': {'frames': 5000, 'timeout_ms': 60000},
                'known_capability_revision': current['capability_revision']}}}
        mcp.process.stdin.write(json.dumps(pending) + '\n')
        mcp.process.stdin.flush()
        time.sleep(.15)
        probe_id = mcp.next_id
        mcp.next_id += 1
        mcp.process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': probe_id, 'method': 'tools/call',
                                           'params': {'name': 'status', 'arguments': {}}}) + '\n')
        mcp.process.stdin.flush()
        deadline = time.monotonic() + 10
        admission = None
        while time.monotonic() < deadline:
            response = json.loads(mcp.responses.get(timeout=max(.001, deadline - time.monotonic())))
            if response.get('id') == request_id:
                raise RuntimeError(f'long native wait terminated before cancellation: {response}')
            if response.get('id') == probe_id:
                result = response.get('result', {})
                if result.get('isError') and result.get('structuredContent', {}).get('error', {}).get('code') == 'busy':
                    admission = {'launch_id': launch_id, 'active_control_busy': True,
                                 'operation': 'wait_for_running_frames'}
                break
        cancelled_at = time.monotonic()
        mcp.process.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/cancelled',
                                          'params': {'requestId': request_id}}) + '\n')
        mcp.process.stdin.flush()
        if not admission:
            raise RuntimeError('could not prove active wait admission before cancellation')
        deadline = time.monotonic() + 12
        while True:
            response = mcp.request('tools/call', {'name': 'status', 'arguments': {}}, timeout=15)
            result = response.get('result', {})
            if not result.get('isError') and 'error' not in response:
                after_cancel = result.get('structuredContent', {})
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f'wait cancellation did not release control: {response}')
            time.sleep(.01)
        if after_cancel.get('state') != 'running' or not after_cancel.get('connected'):
            raise RuntimeError(f'wait cancellation lost the running generation: {after_cancel}')
        control_recovery_seconds = time.monotonic() - cancelled_at
        after_cancel_pixels = snapshot('after-wait-cancel')
        if after_cancel_pixels['buttons'] != 1 or not 0 < (after_cancel_pixels['stick'] & 65535) < 32768:
            raise RuntimeError('wait cancellation changed unrelated persistent input')
        evidence['wait_cancellation'] = {'admission': admission,
            'seconds_until_control_recovered': control_recovery_seconds,
            'guest_after_cancel': after_cancel_pixels}
        debug('set_input', {'port': 0, 'buttons': [], 'axes': {}})
        released = snapshot('released')
        if released['buttons'] != 0 or released['stick'] != 0:
            raise RuntimeError(f'guest did not consume controller release: {released}')
        bounds = touch_bounds
        if bounds:
            for x, y in ((0, 0), (bounds['width'] // 2, bounds['height'] // 2),
                         (bounds['width'] - 1, bounds['height'] - 1)):
                debug('hold_touch', {'x': x, 'y': y})
                touched = snapshot(f'touch-{x}-{y}')
                tx, ty = touched['touch'] & 65535, touched['touch'] >> 16
                if abs(tx - x) > 1 or abs(ty - y) > 1:
                    raise RuntimeError(f'guest touch mapping mismatch: {(x, y)} -> {(tx, ty)}')
                if args.system == '3ds' and touched['bottom_level'] != 192:
                    raise RuntimeError('combined capture did not contain the touched bottom screen')
            debug('release_touch', {})
            touch_released = snapshot('touch-release')
            if touch_released['touch'] != 0xffffffff:
                raise RuntimeError('guest touch release missing')
            if args.system == '3ds' and touch_released['bottom_level'] != 48:
                raise RuntimeError('combined capture did not contain the released bottom screen')
        frozen = None
        unqualified = ['exact stepping', 'capture timeout recovery', 'disconnect input cleanup']
        if 'pause' in status.get('methods', []):
            call('pause')
            path = out / 'frozen.png'
            call('screenshot', {'save_path': str(path)})
            frozen = decode(path, args.system)
            time.sleep(.2)
            path2 = out / 'still-frozen.png'
            call('screenshot', {'save_path': str(path2)})
            if decode(path2, args.system)['frame'] != frozen['frame']:
                raise RuntimeError('guest counter advanced while paused')
        else:
            unqualified.append('paused stability: native pause capability unavailable')
        evidence.update(status='passed', guest_initial=first, guest_held=held,
                        guest_released=released, guest_frozen=frozen,
                        unqualified=unqualified)
    except Exception as error:
        evidence['error'] = str(error)
    finally:
        if mcp:
            if launch_id:
                try:
                    evidence['stop'] = mcp.tool('stop', {'launch_id': launch_id})
                    if evidence['stop'].get('stopped') is not True:
                        raise RuntimeError(f'managed stop did not verify exit: {evidence["stop"]}')
                except Exception as error:
                    evidence.update(status='failed', cleanup_error=str(error))
            try:
                mcp.close()
            except Exception as error:
                evidence.update(status='failed', mcp_exit_error=str(error))
        if runtime_home:
            try:
                collect_runtime_evidence(runtime_home, out)
                if evidence.get('cleanup_error'):
                    evidence['private_runtime_home'] = str(runtime_home)
                elif (runtime_home.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                      and runtime_home.name.startswith('emucap-live-home-') and not runtime_home.is_symlink()):
                    shutil.rmtree(runtime_home)
            except Exception as error:
                evidence.update(status='failed', evidence_error=str(error))
        (out / 'result.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence))
    return 0 if evidence['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())

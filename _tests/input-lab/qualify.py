"""Managed live Input Lab qualification for maintained Nintendo emulator families.

Launch configuration is explicit JSON with the same system/content_path/emulator
arguments as emucap launch. No ROMs, firmware or keys are acquired by this runner.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from observation import decode, require_state, require_handheld_ui

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '_tests/live/mesen2'))
from support import McpProcess
sys.path.insert(0, str(ROOT / '_tests/live/emulator-family'))
from qualify import free_port, collect_runtime_evidence, remove_runtime_home

BUTTONS = {'a': 0, 'b': 1, 'x': 2, 'y': 3, 'l': 4, 'r': 5, 'zl': 6, 'zr': 7,
           'minus': 8, 'select': 8, 'plus': 9, 'start': 9, 'lstick': 10, 'rstick': 11,
           'up': 12, 'down': 13, 'left': 14, 'right': 15, 'sl': 16, 'sr': 17}
AXES = ('stick_x', 'stick_y', 'cstick_x', 'cstick_y')


def validate_capabilities(status, system):
    required_touch = system != 'gba'
    required_axes = system in ('3ds', 'switch', 'switch2')
    if bool(status.get('touch_capability')) != required_touch:
        raise RuntimeError(f'{system}: required touchscreen capability mismatch')
    if bool(status.get('input_axes')) != required_axes:
        raise RuntimeError(f'{system}: required analog capability mismatch')
    buttons = status.get('input_buttons', {})
    buttons = buttons.get('buttons', []) if isinstance(buttons, dict) else buttons
    if system in ('nds', 'gba', '3ds'):
        expected = set('a b select start up down left right l r'.split())
        if system != 'gba':
            expected.update(('x', 'y'))
        if system == '3ds':
            expected.update(('zl', 'zr'))
    else:
        expected = set('a b x y lstick rstick l r zl zr plus minus left up right down'.split())
        # Eden uses ProController; Ryujinx also exposes the Joy-Con rail buttons.
        if status.get('adapter') == 'ryujinx-family-native':
            expected.update(('sl', 'sr'))
    if (not isinstance(buttons, list) or len(set(buttons)) != len(buttons)
            or not expected.issubset(buttons)
            or (system in ('nds', 'gba') and set(buttons) != expected)):
        raise RuntimeError(f'{system}: required button capability mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mcp', type=Path, required=True)
    parser.add_argument('--launch-json', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--approve-indirect-media', action='store_true',
                        help='Approve only this reviewed source-built Ounce ExeFS graph')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    selection = json.loads(args.launch_json.read_text(encoding='utf-8'))
    system = selection['system']
    if system not in ('switch', 'switch2', '3ds', 'nds', 'gba'):
        parser.error('this live runner supports Switch, Switch 2, 3DS, DS and GBA')
    dimensions = {'3ds': (400, 240), 'nds': (256, 192), 'gba': (240, 160)}.get(system, (1280, 720))
    target = {'switch': 1, 'switch2': 2, '3ds': 3, 'nds': 4, 'gba': 5}[system]
    result = {'status': 'failed', 'system': system, 'passed': [], 'unsupported': [],
              'claims': 'guest-observed input only; no exact stepping or hardware proof',
              'content_sha256': hashlib.sha256(Path(selection['content_path']).read_bytes()).hexdigest()}
    content = Path(selection['content_path'])
    manifest_path = content.parent.parent / 'fixture.json' if system == 'switch2' else content.parent / 'fixture.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['content_sha256'] != result['content_sha256'] or manifest['system'] != system:
        raise RuntimeError('fixture manifest does not match selected content/system')
    result['build_id'] = manifest['build_id']
    result['selection'] = selection
    result['mcp_sha256'] = hashlib.sha256(args.mcp.read_bytes()).hexdigest()
    if system in ('nds', 'gba'):
        core = Path(selection['emulator']['core'])
        profile = Path(selection['emulator'].get('profile', core.parent / 'emucap-emulator-build.json'))
        supervisor = Path(selection['emulator'].get('binary', ROOT / 'target/release' /
                          ('emucap-azahar.exe' if os.name == 'nt' else 'emucap-azahar')))
        result['selected_sha256'] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (core, profile, supervisor, ROOT / 'adapters/libretro/bridge.py',
                         ROOT / 'adapters/azahar/bridge.py')}
    mcp, home, launch_id = None, None, None
    try:
        home = Path(tempfile.mkdtemp(prefix='emucap-input-lab-home-'))
        env = dict(os.environ, EMUCAP_REPO_ROOT=str(ROOT), EMUCAP_BROKER='0',
                   EMUCAP_PORT=str(free_port()), EMUCAP_EMU_HOME=str(home))
        mcp = McpProcess(args.mcp.resolve(), env, out / 'mcp.log')
        mcp.initialize()
        plan_selection = {k: v for k, v in selection.items() if k != 'display'}
        plan = mcp.tool('launch_plan', plan_selection)
        if plan.get('indirect_media', {}).get('state') == 'review_required':
            if not args.approve_indirect_media:
                raise RuntimeError('reviewed composite source-built media needs explicit approval')
            selection['indirect_media_approval'] = plan['next_action']['then_call']['arguments']['indirect_media_approval']
        launched = mcp.tool('launch', selection)
        if not launched.get('launched'):
            raise RuntimeError(f'launch rejected: {launched}')
        launch_id = launched['runtime_instance']['launch_id']
        status = mcp.tool('status', {})
        (out / 'status.json').write_text(json.dumps(status, indent=2)+'\n', encoding='utf-8')
        if status.get('contracts', {}).get('state') != 'validated':
            raise RuntimeError('capability contract is not validated')
        validate_capabilities(status, system)
        if status.get('state') != 'running':
            mcp.tool('resume', {})

        def debug(operation, arguments):
            current = mcp.tool('status', {})
            return mcp.tool('debug', {'operation': operation, 'arguments': arguments,
                                    'known_capability_revision': current['capability_revision']})

        last = 0
        def snapshot(label, expected=None, tolerance=0):
            nonlocal last
            deadline = time.monotonic() + 25
            while True:
                terminal = debug('wait_for_running_frames', {'frames': 3, 'timeout_ms': 10000})
                if terminal.get('status') != 'completed':
                    raise RuntimeError(f'progress wait did not complete: {terminal}')
                path = out / (label + '.png')
                mcp.tool('screenshot', {'save_path': str(path)})
                try:
                    observed = decode(path, *dimensions, target=target, build_id=manifest['build_id'])
                    if system in ('nds', 'gba'):
                        require_handheld_ui(path, dimensions[0])
                    if expected is not None:
                        require_state(observed, expected, after=last, axis_tolerance=tolerance)
                    elif not 0 < (observed['sequence'] - last) & 0xffffffff < 0x80000000:
                        raise AssertionError('guest sequence did not advance')
                    break
                except (ValueError, AssertionError) as error:
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f'{label}: {error}') from error
            last = observed['sequence']
            (out / (label + '.json')).write_text(json.dumps(observed, indent=2)+'\n', encoding='utf-8')
            result['passed'].append(label)
            return observed

        neutral = {'buttons': 0, 'axes': [0]*4, 'triggers': [0, 0], 'touch': None, 'port': 0}
        debug('set_input', {'port': 0, 'buttons': [], 'axes': {}})
        has_touch = 'touch_capability' in status
        if has_touch:
            debug('release_touch', {})
        first = snapshot('neutral', neutral)
        snapshot('progress', neutral)
        advertised_buttons = status['input_buttons']
        if isinstance(advertised_buttons, dict):
            advertised_buttons = advertised_buttons['buttons']
        for button in advertised_buttons:
            if button not in BUTTONS:
                raise RuntimeError(f'advertised button has no independent guest mapping: {button}')
            debug('set_input', {'port': 0, 'buttons': [button], 'axes': {}})
            expected = dict(neutral, buttons=1 << BUTTONS[button])
            snapshot(button + '-hold', expected)
            snapshot(button + '-sustained', expected)
            debug('set_input', {'port': 0, 'buttons': [], 'axes': {}})
            snapshot(button + '-release', neutral)
        # Independent native API scales; do not learn expected values from the guest.
        maximum = 156 if system == '3ds' else 32767
        for index, axis in enumerate(AXES if status.get('input_axes') else ()):
            if system == '3ds' and index >= 2 and not first['valid'] & 4:
                raise RuntimeError('advertised C-stick unavailable in native guest IRRST service')
            for value in (-32767, -16384, -8192, 8192, 16384, 32767):
                debug('set_input', {'port': 0, 'buttons': [], 'axes': {axis: value}})
                expected_axes = [0]*4
                expected_axes[index] = round(value * maximum / 32767)
                if index % 2 and system == '3ds':
                    expected_axes[index] *= -1  # Azahar libretro host Y down -> native HID Y up.
                snapshot(f'{axis}-{value}', dict(neutral, axes=expected_axes), tolerance=3 if system == '3ds' else 1)
                debug('set_input', {'port': 0, 'buttons': [], 'axes': {}})
                snapshot(f'{axis}-{value}-release', neutral)
        if has_touch:
            bounds = status['touch_capability']
            width, height = bounds['width'], bounds['height']
            edges = bounds.get('bounds') or {'x_min': 0, 'x_max': width-1, 'y_min': 0, 'y_max': height-1}
            points = [(edges['x_min'], edges['y_min']), (edges['x_max'], edges['y_min']),
                      (edges['x_max'], edges['y_max']), (edges['x_min'], edges['y_max']),
                      (width//2, height//2)]
            for i, (x, y) in enumerate(points):
                debug('hold_touch', {'x': x, 'y': y})
                snapshot(f'touch-{i}', dict(neutral, touch=[x, y]))
            debug('release_touch', {})
            snapshot('touch-release', neutral)
        combo = ['a', 'b', 'l', 'r']
        combined_axes = {'stick_x': 16384, 'cstick_y': -8192} if status.get('input_axes') else {}
        debug('set_input', {'port': 0, 'buttons': combo, 'axes': combined_axes})
        if has_touch:
            debug('hold_touch', {'x': width//2, 'y': height//2})
        expected_axes = [round(maximum*16384/32767), 0, 0,
                         round(maximum*8192/32767) * (1 if system == '3ds' else -1)] if combined_axes else [0]*4
        combined = dict(neutral, buttons=sum(1 << BUTTONS[b] for b in combo),
                        axes=expected_axes, touch=[width//2, height//2] if has_touch else None)
        snapshot('combined', combined,
                 tolerance=3 if system == '3ds' else 1)
        if system in ('nds', 'gba'):
            result['rejected_unsupported_requests'] = []
            for label, operation, arguments in [
                ('other-port', 'set_input', {'port': 1, 'buttons': []}),
                ('analog-axis', 'set_input', {'buttons': [], 'axes': {'stick_x': 1}}),
                ('timed-touch' if has_touch else 'touch-absent',
                 'pulse_touch_while_running' if has_touch else 'hold_touch', {'x': 1, 'y': 1, 'frames': 1}),
            ]:
                current = mcp.tool('status', {})
                response = mcp.request('tools/call', {'name': 'debug', 'arguments': {
                    'operation': operation, 'arguments': arguments,
                    'known_capability_revision': current['capability_revision']}})
                (out / (label + '-rejection.json')).write_text(json.dumps(response, indent=2)+'\n', encoding='utf-8')
                if not response.get('error') and not response.get('result', {}).get('isError'):
                    raise AssertionError(f'unsupported request accepted: {label}')
                result['rejected_unsupported_requests'].append(label)
                snapshot(label + '-state-preserved', combined)
        debug('set_input', {'port': 0, 'buttons': [], 'axes': {}})
        if has_touch:
            debug('release_touch', {})
        snapshot('final-release', neutral)
        result['unsupported'] = ['other controller ports (adapter port 0 only)',
                                 'analog triggers (not present on these controllers)', 'exact frame stepping']
        result['status'] = 'passed'
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        cleanup_errors = []
        if mcp:
            try:
                if launch_id:
                    stopped = mcp.tool('stop', {'launch_id': launch_id})
                    result['stop'] = stopped
                    if not stopped.get('stopped') or stopped.get('status') != 'completed':
                        raise RuntimeError('managed generation did not report completed stop')
            except Exception as error:
                cleanup_errors.append(str(error))
            finally:
                try:
                    mcp.close()
                except Exception as error:
                    cleanup_errors.append(str(error))
        if home:
            try:
                collect_runtime_evidence(home, out)
                if not cleanup_errors and result['status'] == 'passed':
                    remove_runtime_home(home)
            except Exception as error:
                cleanup_errors.append(str(error))
            if cleanup_errors or result['status'] != 'passed':
                result['preserved_runtime_home'] = str(home)
        if cleanup_errors:
            result['cleanup_error'] = '; '.join(cleanup_errors)
            result['status'] = 'failed'
        (out / 'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    if result['status'] != 'passed':
        raise RuntimeError(result.get('cleanup_error', 'qualification failed'))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

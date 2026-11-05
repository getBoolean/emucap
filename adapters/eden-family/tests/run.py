#!/usr/bin/env python3
"""Compile and exercise the shared native producer with synthetic owner-thread hooks."""
import argparse
import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
import zlib

HERE = pathlib.Path(__file__).resolve().parent
ADAPTER = HERE.parent
COMMON = ADAPTER.parent / '_common'
JSON_URL = 'https://raw.githubusercontent.com/nlohmann/json/v3.12.0/single_include/nlohmann/json.hpp'
JSON_SHA256 = 'aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63'


def exact(sock, size):
    data = b''
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise AssertionError('native producer closed during authentication')
        data += part
    return data


def proof(key, *fields):
    message = b''.join(struct.pack('>Q', len(field)) + field for field in fields)
    return hmac.new(key.encode(), message, hashlib.sha256).digest()


def authenticate(sock, port, key, runtime):
    header = lambda kind: b'ECFA' + bytes([1, kind, 1])
    challenge = header(1) + struct.pack('>H', port) + secrets.token_bytes(16)
    sock.sendall(challenge)
    producer = exact(sock, 88)
    assert producer[:7] == header(2)
    assert producer[7:40] == runtime.encode()
    transcript = challenge + producer[7:56]
    domain = b'emucap-producer-front-auth-v1'
    assert hmac.compare_digest(producer[56:], proof(key, domain, b'producer', transcript))
    sock.sendall(header(3) + proof(key, domain, b'listener', transcript))
    assert exact(sock, 39) == header(4) + proof(key, domain, b'commit', transcript)
    sock.sendall(header(5))


def await_file(path, predicate):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            value = json.loads(path.read_text())
            if predicate(value):
                return
        except (OSError, json.JSONDecodeError):
            pass
        time.sleep(0.01)
    raise AssertionError(f'native owner did not reach expected file state: {path.name}')


def exercise(binary, root):
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(10)
    port = listener.getsockname()[1]
    key = 'front-direct-' + secrets.token_hex(32)
    runtime = 'launch-' + '0' * 26
    profile = {'schema': 'emucap-emulator-build/v1', 'family': 'eden-family',
               'bridge_api': 1, 'fork': 'fixture', 'revision': 'a' * 40,
               'systems': ['switch'], 'renderers': ['vulkan']}
    profile_path = root / 'profile.json'
    profile_path.write_text(json.dumps(profile))
    env = dict(os.environ, EMUCAP_PORT=str(port), EMUCAP_SESSION_TOKEN=key,
               EMUCAP_LAUNCH_ID=runtime, EMUCAP_SYSTEM='switch', EMUCAP_RENDERER='vulkan',
               EMUCAP_USER_ROOT=str(root), EMUCAP_BUILD_PROFILE=str(profile_path))
    # Native identity is compiled into the producer; the selected JSON is only an expectation.
    profile_path.write_text(json.dumps(dict(profile, bridge_api=2)))
    rejected = subprocess.run([str(binary)], env=env, cwd=root, timeout=5, capture_output=True)
    assert rejected.returncode == 64
    profile_path.write_text(json.dumps(profile))
    rejected = subprocess.run([str(binary)], env=dict(env, EMUCAP_SYSTEM='switch2'),
                              cwd=root, timeout=5, capture_output=True)
    assert rejected.returncode == 64
    process = subprocess.Popen([str(binary)], env=env, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        sock, _ = listener.accept()
        sock.settimeout(10)
        authenticate(sock, port, key, runtime)
        stream = sock.makefile('rb')
        next_id = 1

        def send(method, params=None):
            nonlocal next_id
            identifier = next_id
            next_id += 1
            sock.sendall((json.dumps({'v': 1, 'id': identifier, 'method': method,
                                     'params': params or {}}) + '\n').encode())
            return identifier

        def terminal(identifier):
            while True:
                value = json.loads(stream.readline(8 * 1024 * 1024 + 1))
                assert value['id'] == identifier, value
                if value.get('result', {}).get('status') != 'working':
                    return value

        hello = terminal(send('hello'))['result']
        assert hello['adapter'] == 'eden-family-native'
        assert 'session_token' not in hello and key not in json.dumps(hello)
        assert 'step' not in hello['methods'] and 'pause' not in hello['methods']
        assert hello['progress_capability']['domain'] == 'native_render_present'
        assert pathlib.Path(hello['managed_user_root']).resolve() == root.resolve()
        assert hello['contracts']['active_exceptions'] == ['eden.input-touch.persistent-only']
        assert hello['input_buttons'] == 'a b x y lstick rstick l r zl zr plus minus left up right down'.split()
        for unavailable in ('sl', 'sr', 'home', 'capture'):
            assert not terminal(send('set_input', {'port': 0, 'buttons': [unavailable]}))['ok']
        assert terminal(send('set_input', {'port': 0, 'buttons': ['a'], 'axes': {'stick_x': 32767}}))['ok']
        await_file(root / 'input.json', lambda value: value == {'a': True, 'stick_x': 32767})
        assert hello['touch_capability']['bounds'] == {'x_min': 15, 'x_max': 1264, 'y_min': 15, 'y_max': 704}
        assert terminal(send('touch', {'port': 0, 'x': 1264, 'y': 704, 'release': False}))['ok']
        await_file(root / 'touch.json', lambda value: value == {'x': 1264, 'y': 704})
        assert not terminal(send('touch', {'port': 0, 'x': 0, 'y': 0, 'release': False}))['ok']
        assert json.loads((root / 'touch.json').read_text()) == {'x': 1264, 'y': 704}
        image = terminal(send('screenshot'))['result']
        png = base64.b64decode(image['png_base64'])
        assert png[:8] == b'\x89PNG\r\n\x1a\n'
        chunks = []
        offset = 8
        while offset < len(png):
            size = struct.unpack('>I', png[offset:offset + 4])[0]
            kind = png[offset + 4:offset + 8]
            data = png[offset + 8:offset + 8 + size]
            if kind == b'IDAT':
                chunks.append(data)
            offset += 12 + size
        assert zlib.decompress(b''.join(chunks))[:4] == b'\0\xff\0\0'
        assert image['capture_id'].startswith(runtime + '-capture-')
        observed = terminal(send('wait_for_running_frames', {'frames': 2, 'timeout_ms': 1000}))['result']
        assert observed['status'] == 'completed' and observed['requested'] == 2
        assert observed['observed'] == observed['end'] - observed['start'] >= 2
        assert observed['overshoot'] == observed['observed'] - 2 and observed['state'] == 'running'
        (root / 'stalled').touch()
        time.sleep(0.05)
        stalled = terminal(send('wait_for_running_frames', {'frames': 1, 'timeout_ms': 30}))['result']
        assert stalled['status'] == 'timed_out' and stalled['observed'] == 0
        (root / 'stalled').unlink()
        # A timeout retains the renderer's destination until its late callback.
        (root / 'capture_delay_ms').write_text('6000')
        expired = terminal(send('screenshot'))
        assert not expired['ok'] and expired['error']['kind'] == 'timeout'
        busy = terminal(send('screenshot'))
        assert not busy['ok'] and busy['error']['kind'] == 'busy'
        time.sleep(1.2)
        (root / 'capture_delay_ms').unlink()
        image = terminal(send('screenshot'))['result']
        (root / 'paused').touch()
        time.sleep(0.05)
        cached = terminal(send('screenshot'))['result']
        assert not cached['fresh'] and cached['capture_id'] == image['capture_id']
        assert not terminal(send('wait_for_running_frames', {'frames': 1, 'timeout_ms': 100}))['ok']
        (root / 'paused').unlink()
        time.sleep(0.05)
        owner = {'runtime': runtime, 'owner_id': 'owner', 'operation_id': 'wait'}
        waiting = send('wait_for_running_frames', {'frames': 5000, 'timeout_ms': 5000, '_control': owner})
        cancel_id = send('cancel_operation', owner)
        cancel = json.loads(stream.readline())
        interrupted = json.loads(stream.readline())
        assert cancel['id'] == cancel_id and cancel['result']['status'] == 'requested'
        assert interrupted['id'] == waiting and interrupted['result']['status'] == 'interrupted'
        # A waiting observer owns no input. Cancellation must preserve the explicit hold.
        await_file(root / 'input.json', lambda value: value['a'])
        attachment = {'broker_instance': 'fixture-broker', 'registration': 1, 'session': 1}
        sock.sendall((json.dumps({'_control_session': {'kind': 'attach', 'runtime': runtime,
                                                     'attachment': attachment}}) + '\n').encode())
        result = terminal(send('set_input', {'buttons': ['a'], '_control_attachment': attachment}))
        assert result['ok']
        sock.sendall((json.dumps({'_control_session': {'kind': 'detach', 'runtime': runtime,
                                                     'attachment': attachment}}) + '\n').encode())
        await_file(root / 'input.json', lambda value: not value['a'])
        await_file(root / 'touch.json', lambda value: value is None)
        attachment = dict(attachment, session=2)
        sock.sendall((json.dumps({'_control_session': {'kind': 'attach', 'runtime': runtime,
                                                     'attachment': attachment}}) + '\n').encode())
        assert terminal(send('set_input', {'buttons': ['a'], '_control_attachment': attachment}))['ok']
        # Transport EOF releases persistent state through the native owner, too.
        stream.close()
        sock.close()
        await_file(root / 'input.json', lambda value: not value['a'])
        (root / 'quit').touch()
        process.wait(timeout=5)
        assert process.returncode == 0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        listener.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', default=os.environ.get('CXX', 'g++'))
    parser.add_argument('--json-include', type=pathlib.Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='emucap-eden-native-') as temporary:
        root = pathlib.Path(temporary)
        include = args.json_include or root / 'include'
        if not args.json_include:
            destination = include / 'nlohmann' / 'json.hpp'
            destination.parent.mkdir(parents=True)
            data = urllib.request.urlopen(JSON_URL, timeout=30).read()
            if hashlib.sha256(data).hexdigest() != JSON_SHA256:
                raise RuntimeError('pinned JSON header digest mismatch')
            destination.write_bytes(data)
        suffix = '.exe' if os.name == 'nt' else ''
        for source in ('bridge_tests', 'endpoint_fixture'):
            binary = root / (source + suffix)
            command = [args.cxx, '-std=c++20', '-O1', '-Wall', '-Wextra', '-Werror', '-pthread',
                       '-I' + str(ADAPTER / 'native'), '-I' + str(COMMON), '-I' + str(include),
                       str(HERE / (source + '.cpp')), str(ADAPTER / 'native' / 'EmucapBridge.cpp'),
                       str(COMMON / 'emucap_native_failure.cpp'), '-o', str(binary)]
            if os.name == 'nt':
                command.append('-lws2_32')
            subprocess.run(command, check=True)
            if source == 'bridge_tests':
                subprocess.run([str(binary)], check=True)
            else:
                fixture_root = root / 'unicode-é-橋'
                fixture_root.mkdir()
                exercise(binary, fixture_root)
        print('Authenticated producer, owner-thread input/touch, PNG capture, wait cancellation and detach passed.')
        print('Synthetic hooks only; no real emulator or guest qualification.')


if __name__ == '__main__':
    main()

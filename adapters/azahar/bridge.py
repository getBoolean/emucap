"""Private single-owner libretro worker. The Rust host owns managed transport."""
import argparse
import base64
import ctypes as C
import json
import os
import pathlib
import queue
import struct
import sys
import threading
import time
import zlib

MAX_REQUEST_BYTES = 64 * 1024
MAX_FRAME_BYTES = 8 * 1024 * 1024
MAX_PNG_BYTES = ((MAX_FRAME_BYTES - 64 * 1024) * 3) // 4
BUTTONS = dict(zip('b y select start up down left right a x l r zl zr'.split(), range(14)))
AXES = ('stick_x', 'stick_y', 'cstick_x', 'cstick_y')
OPTIONS = {b'citra_graphics_api': b'Software', b'citra_is_new_3ds': b'New 3DS',
           b'citra_layout_option': b'default', b'citra_resolution_factor': b'1',
           b'citra_enable_touch_touchscreen': b'enabled', b'citra_analog_function': b'c_stick'}
OPTIONS.update({b'citra_enable_mouse_touchscreen': b'disabled', b'citra_enable_motion': b'disabled',
                b'citra_enable_touch_pointer_timeout': b'disabled', b'citra_swap_screen': b'Top'})


def png(width, height, rows):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    result = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
              + chunk(b'IDAT', zlib.compress(b''.join(b'\0' + row for row in rows))) + chunk(b'IEND', b''))
    if len(result) > MAX_PNG_BYTES:
        raise RuntimeError('Software PNG exceeds protocol size bound')
    return result


class Variable(C.Structure):
    _fields_ = [('key', C.c_char_p), ('value', C.c_char_p)]


class Game(C.Structure):
    _fields_ = [('path', C.c_char_p), ('data', C.c_void_p), ('size', C.c_size_t), ('meta', C.c_char_p)]


class SystemInfo(C.Structure):
    _fields_ = [('name', C.c_char_p), ('version', C.c_char_p), ('extensions', C.c_char_p),
                ('need_fullpath', C.c_bool), ('block_extract', C.c_bool)]


class Geometry(C.Structure):
    _fields_ = [('width', C.c_uint), ('height', C.c_uint), ('max_width', C.c_uint),
                ('max_height', C.c_uint), ('aspect', C.c_float)]


class Timing(C.Structure):
    _fields_ = [('fps', C.c_double), ('sample_rate', C.c_double)]


class AvInfo(C.Structure):
    _fields_ = [('geometry', Geometry), ('timing', Timing)]


class CoreFailure(RuntimeError):
    pass


class Bridge:
    adapter = 'azahar-libretro'
    system = '3ds'
    buttons_map = BUTTONS
    axes_names = AXES
    initial_geometry = (400, 480)
    touch_size = (320, 240)
    options = OPTIONS

    def __init__(self, core, rom, directory, profile=None):
        core_path = pathlib.Path(core).resolve()
        self.dll_directory = os.add_dll_directory(str(core_path.parent)) if sys.platform == 'win32' else None
        self.core = C.CDLL(str(core_path))
        self.buttons, self.touch, self.axes = set(), None, {}
        self.frame, self.presentations, self.image = 0, 0, None
        self.pixel_format, self.failure = 0, None
        self.initialized, self.loaded, self.closed = False, False, False
        self.callbacks, self.option_values = [], dict(self.options)
        self.directory = str(pathlib.Path(directory).resolve()).encode()
        self.rom = str(pathlib.Path(rom).resolve()).encode()
        self.geometry = self.initial_geometry
        pathlib.Path(directory).mkdir(parents=True, exist_ok=True)
        signatures = {
            'retro_api_version': (C.c_uint, []),
            'retro_get_system_info': (None, [C.POINTER(SystemInfo)]),
            'retro_get_system_av_info': (None, [C.POINTER(AvInfo)]),
            'retro_init': (None, []), 'retro_deinit': (None, []),
            'retro_load_game': (C.c_bool, [C.POINTER(Game)]),
            'retro_unload_game': (None, []), 'retro_run': (None, []),
            'emucap_get_build_profile_json': (C.c_char_p, []),
        }
        if self.system == '3ds':
            signatures.update({'emucap_get_effective_user_root': (C.c_char_p, []),
                               'emucap_get_last_error': (C.c_char_p, [])})
        for name, (result, arguments) in signatures.items():
            function = getattr(self.core, name)
            function.restype, function.argtypes = result, arguments
        selected_path = pathlib.Path(profile) if profile else pathlib.Path(core).parent / 'emucap-emulator-build.json'
        with selected_path.open('rb') as source:
            selected_bytes = source.read(128 * 1024 + 1)
        if len(selected_bytes) > 128 * 1024:
            raise RuntimeError('Selected core build profile is oversized')
        selected = json.loads(selected_bytes)
        self.native_profile = json.loads(self.core.emucap_get_build_profile_json() or b'null')
        if not isinstance(self.native_profile, dict) or self.native_profile != selected:
            raise RuntimeError('Selected profile does not match compiled core build profile')
        if self.core.retro_api_version() != 1:
            raise RuntimeError('Unsupported libretro API version')
        info = SystemInfo()
        self.core.retro_get_system_info(C.byref(info))
        if not info.need_fullpath and self.system == '3ds':
            raise RuntimeError('This worker requires need_fullpath=true')
        if pathlib.Path(rom).suffix.lstrip('.').lower() not in (info.extensions or b'').decode().split('|'):
            raise ValueError('Guest extension is not supported by the core')
        self.system_info = {'name': (info.name or b'').decode(errors='replace'),
                            'version': (info.version or b'').decode(errors='replace')}

        def bind(name, signature, callback, fallback=None):
            def safe(*args):
                try:
                    return callback(*args)
                except BaseException as error:
                    self.failure = f'Native callback failed: {error}'
                    return fallback
            cb = signature(safe)
            self.callbacks.append(cb)
            function = getattr(self.core, name)
            function.restype, function.argtypes = None, [signature]
            function(cb)

        bind('retro_set_environment', C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p), self.environment, False)
        bind('retro_set_video_refresh', C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t), self.video)
        bind('retro_set_input_poll', C.CFUNCTYPE(None), lambda: None)
        bind('retro_set_input_state', C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint), self.input, 0)
        bind('retro_set_audio_sample', C.CFUNCTYPE(None, C.c_int16, C.c_int16), lambda *_: None)
        bind('retro_set_audio_sample_batch', C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t), lambda _, n: n, 0)
        try:
            self.initialized = True
            self.core.retro_init()
            self.check_failure()
            self.content_buffer = None if info.need_fullpath else C.create_string_buffer(pathlib.Path(rom).read_bytes())
            game = Game(self.rom, C.cast(self.content_buffer, C.c_void_p) if self.content_buffer else None,
                        len(self.content_buffer) - 1 if self.content_buffer else 0, None)
            if not self.core.retro_load_game(C.byref(game)):
                raise RuntimeError('Core rejected homebrew fixture')
            self.loaded = True
            self.check_failure()
            actual = self.core.emucap_get_effective_user_root() if self.system == '3ds' else self.directory
            expected = pathlib.Path(directory).resolve() / 'Azahar' if self.system == '3ds' else pathlib.Path(directory).resolve()
            try:
                storage_matches = actual and pathlib.Path(os.fsdecode(actual)).resolve(strict=True) == expected
            except OSError:
                storage_matches = False
            if not storage_matches:
                raise RuntimeError('Unexpected effective core user root; managed storage was not established')
            self.effective_core_user_root = str(pathlib.Path(os.fsdecode(actual)).resolve(strict=True))
            av = AvInfo()
            self.core.retro_get_system_av_info(C.byref(av))
            self.set_geometry(av.geometry)
        except BaseException:
            self.close()
            raise

    def check_failure(self):
        if self.failure:
            raise CoreFailure(self.failure)
        if self.system == '3ds' and hasattr(self, 'core'):
            error = self.core.emucap_get_last_error()
            if error:
                raise CoreFailure(error.decode(errors='replace'))

    def run_one(self):
        self.core.retro_run()
        self.frame += 1
        self.check_failure()

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.loaded:
                self.loaded = False
                self.core.retro_unload_game()
        finally:
            if self.initialized:
                self.initialized = False
                self.core.retro_deinit()

    def set_geometry(self, geometry):
        if not 0 < geometry.width <= 4096 or not 0 < geometry.height <= 4096:
            raise ValueError('Invalid software geometry')
        if (geometry.width, geometry.height) != self.initial_geometry:
            raise ValueError(f'Software mapping requires the pinned {self.initial_geometry} layout')
        self.geometry = (geometry.width, geometry.height)

    def environment(self, cmd, data):
        if cmd == 7:
            self.failure = 'Core requested shutdown'
            return True
        if not data:
            return False
        if cmd in (9, 31):
            C.cast(data, C.POINTER(C.c_char_p))[0] = self.directory
            return True
        if cmd == 3:
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        if cmd == 10:
            value = C.cast(data, C.POINTER(C.c_uint))[0]
            if value not in (0, 1, 2):
                return False
            self.pixel_format = value
            return True
        if cmd == 15:
            var = C.cast(data, C.POINTER(Variable)).contents
            var.value = self.option_values.get(var.key)
            return var.value is not None
        if cmd == 16:
            definitions = C.cast(data, C.POINTER(Variable))
            for index in range(1024):
                var = definitions[index]
                if not var.key:
                    return True
                if var.key not in self.option_values and var.value and b'; ' in var.value:
                    self.option_values[bytes(var.key)] = var.value.split(b'; ', 1)[1].split(b'|', 1)[0]
            raise ValueError('Unterminated core option table')
        if cmd == 17:
            C.cast(data, C.POINTER(C.c_bool))[0] = False
            return True
        if cmd == 37:
            self.set_geometry(C.cast(data, C.POINTER(Geometry)).contents)
            return True
        if cmd in (11, 18, 35):
            return True
        return False

    def input(self, port, device, index, key):
        if port != 0:
            return 0
        if device == 1:
            return int(key in self.buttons)
        if device == 5 and index < 2 and key < 2:
            return getattr(self, 'axes', {}).get(self.axes_names[index * 2 + key], 0) if self.axes_names else 0
        if device == 6 and index == 0 and self.touch is not None:
            x, y = self.touch
            return (round((x + 40.5) * 65534 / 400 - 32767),
                    round((y + 240.5) * 65534 / 480 - 32767), 1)[key] if key < 3 else 0
        return 0

    def video(self, data, width, height, pitch):
        if not data:
            return
        if data == C.c_void_p(-1).value:
            self.failure = 'Hardware framebuffer unsupported; select Software renderer'
            return
        if not 0 < width <= 4096 or not 0 < height <= 4096:
            self.failure = 'Invalid video dimensions'
            return
        size = 4 if self.pixel_format == 1 else 2
        if pitch < width * size or pitch > 1024 * 1024:
            self.failure = 'Invalid video pitch'
            return
        # libretro owns the buffer only until this callback returns.
        rows = tuple(C.string_at(data + y * pitch, width * size) for y in range(height))
        self._frame_snapshot = (self.pixel_format, width, height, rows)
        self._image = None
        self.presentations = getattr(self, 'presentations', 0) + 1

    @property
    def image(self):
        if self._image is None and self._frame_snapshot is not None:
            pixel_format, width, height, native_rows = self._frame_snapshot
            size = 4 if pixel_format == 1 else 2
            rows = []
            try:
                for raw in native_rows:
                    row = bytearray()
                    for x in range(width):
                        value = int.from_bytes(raw[x*size:(x+1)*size], sys.byteorder)
                        if size == 4:
                            rgb = ((value >> 16) & 255, (value >> 8) & 255, value & 255)
                        else:
                            bits = 6 if pixel_format == 2 else 5
                            rgb = (((value >> (bits+5)) & 31)*255//31,
                                   ((value >> 5) & ((1<<bits)-1))*255//((1<<bits)-1), (value & 31)*255//31)
                        row.extend(rgb)
                    rows.append(bytes(row))
                self._image = (width, height, png(width, height, rows))
            except Exception as error:
                self.failure = f'Software capture encoding failed: {error}'
                raise CoreFailure(self.failure) from error
        return self._image

    @image.setter
    def image(self, value):
        self._image = value
        self._frame_snapshot = None

    def validate_touch(self, touch):
        if self.touch_size is None:
            if touch is not None:
                raise NotImplementedError('This system has no touchscreen')
            return
        width, height = self.touch_size
        if touch is not None and (not isinstance(touch, list) or len(touch) != 2 or
                                  any(type(v) is not int for v in touch) or
                                  not 0 <= touch[0] < width or not 0 <= touch[1] < height):
            raise ValueError(f'Touch must be bottom-screen [x,y], {width}x{height}')

    def request(self, method, params):
        if not isinstance(params, dict):
            raise ValueError('params must be an object')
        self.check_failure()
        if method == 'hello':
            return {'protocol_version': 1, 'adapter': self.adapter, 'system': self.system,
                    'renderer': 'software', 'core': self.system_info, 'geometry': list(self.geometry),
                    'host_build': self.native_profile, 'effective_core_user_root': self.effective_core_user_root,
                    'input_buttons': list(self.buttons_map), 'touch_size': self.touch_size,
                    'methods': ['hello', 'status', 'set_input', 'touch', 'screenshot']}
        if method == 'status':
            return {'host_run_calls': self.frame, 'software_presentations': getattr(self, 'presentations', 0),
                    'paused': False, 'state': 'running',
                    'timing': 'software callback presentations; guest halt/exact stepping unqualified'}
        if method == 'set_input':
            names, axes = params.get('buttons', []), params.get('axes', {})
            if params.get('port', 0) != 0 or type(params.get('port', 0)) is not int:
                raise ValueError('Only controller port zero is supported')
            if not isinstance(names, list) or any(not isinstance(name, str) or name not in self.buttons_map for name in names):
                raise ValueError('Unknown button')
            if not isinstance(axes, dict) or any(name not in self.axes_names or type(value) is not int or
                                               not -32767 <= value <= 32767 for name, value in axes.items()):
                raise ValueError('Invalid controller axes')
            touch = params.get('touch')
            self.validate_touch(touch)
            self.buttons, self.axes = {self.buttons_map[name] for name in names}, dict(axes)
            if 'touch' in params:
                self.touch = touch
            return {'released': not names and not axes}
        if method == 'touch':
            if self.touch_size is None:
                raise NotImplementedError('This system has no touchscreen')
            if params.get('port', 0) != 0 or type(params.get('port', 0)) is not int:
                raise ValueError('Only touch port zero is supported')
            if params.get('frames') is not None:
                raise NotImplementedError('Timed touch is not qualified')
            release = params.get('release', False)
            if type(release) is not bool:
                raise ValueError('release must be boolean')
            if release:
                self.touch = None
            else:
                touch = [params.get('x'), params.get('y')]
                self.validate_touch(touch)
                self.touch = touch
            return {'released': release}
        if method == 'run_frames':
            count = params.get('count', 1)
            if type(count) is not int or not 1 <= count <= 120:
                raise ValueError('count must be 1..120')
            for _ in range(count):
                self.run_one()
            return {'host_run_calls': self.frame, 'software_presentations': self.presentations}
        if method == 'screenshot':
            if self.image is None:
                raise RuntimeError('No software video frame received')
            w, h, data = self.image
            return {'width': w, 'height': h, 'format': 'png', 'software_presentations': self.presentations,
                    'freshness': 'last_completed_software_callback',
                    'png_base64': base64.b64encode(data).decode()}
        raise NotImplementedError(method)


def serve(bridge, source, output, continuous=False):
    # The reader never calls the core. Every ABI call, including init/run/close, belongs
    # to the main thread; commands apply between retro_run calls without a CPU halt claim.
    incoming = queue.Queue(maxsize=16)
    if continuous:
        def read_requests():
            try:
                while True:
                    line = source.readline(MAX_REQUEST_BYTES + 2)
                    incoming.put(line)
                    if not line or len(line) > MAX_REQUEST_BYTES or not line.endswith(b'\n'):
                        return
            except BaseException as error:
                incoming.put(error)
        threading.Thread(target=read_requests, name='private-request-reader', daemon=True).start()
    next_frame = time.monotonic() + 1 / 60
    while True:
        if continuous:
            if time.monotonic() >= next_frame:
                bridge.run_one()
                next_frame = max(next_frame + 1 / 60, time.monotonic())
            try:
                line = incoming.get(timeout=max(0, next_frame - time.monotonic()))
            except queue.Empty:
                bridge.run_one()
                # Pacing is host wall-clock scheduling, not deterministic guest time.
                next_frame = max(next_frame + 1 / 60, time.monotonic())
                continue
            if isinstance(line, BaseException):
                raise line
        else:
            line = source.readline(MAX_REQUEST_BYTES + 2)
        if not line:
            return
        if len(line) > MAX_REQUEST_BYTES or not line.endswith(b'\n'):
            raise ValueError('Oversized or truncated worker request; channel retired')
        req = {}
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError('Request must be an object')
            req = value
            if type(req.get('v')) is not int or req['v'] != 1:
                raise ValueError('Expected protocol v1')
            if type(req.get('id')) is not int or not 0 <= req['id'] <= (1 << 64) - 1:
                raise ValueError('id must be an unsigned 64-bit integer')
            if not isinstance(req.get('method'), str):
                raise ValueError('method must be a string')
            result = bridge.request(req['method'], req.get('params', {}))
            reply = {'id': req['id'], 'ok': True, 'result': result}
        except Exception as exc:
            request_id = req.get('id', 0)
            if type(request_id) is not int or not 0 <= request_id <= (1 << 64) - 1:
                request_id = 0
            reply = {'id': request_id, 'ok': False, 'error': {
                'kind': ('unsupported' if isinstance(exc, NotImplementedError) else
                         'native_failure' if isinstance(exc, CoreFailure) else
                         'bad_params' if isinstance(exc, ValueError) else 'adapter_error'),
                'message': str(exc)}}
        encoded = (json.dumps(reply, separators=(',', ':')) + '\n').encode()
        if len(encoded) > MAX_FRAME_BYTES:
            raise ValueError('Worker response exceeds protocol frame bound')
        output.write(encoded)
        output.flush()


def main(bridge_type=Bridge):
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--core', required=True)
    parser.add_argument('--rom', required=True)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--profile')
    parser.add_argument('--supervisor-pid', type=int)
    parser.add_argument('--supervisor-start')
    args = parser.parse_args()
    if args.supervisor_pid:
        guard_supervisor(args.supervisor_pid, args.supervisor_start)
    with os.fdopen(os.dup(sys.stdout.fileno()), 'wb', buffering=0) as output:
        sys.stdout.flush()
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        if sys.platform == 'win32':
            # MinGW's MSVCRT descriptors are separate from Python's UCRT table.
            # Redirect both before loading a core so native logs cannot use the
            # original protocol handle (or the handle closed by os.dup2).
            runtime = C.CDLL('msvcrt')
            runtime._dup2.argtypes = [C.c_int, C.c_int]
            runtime._dup2.restype = C.c_int
            if runtime._dup2(2, 1) != 0:
                raise RuntimeError('Cannot redirect native diagnostic output')
        bridge = bridge_type(args.core, args.rom, args.directory, args.profile)
        try:
            serve(bridge, sys.stdin.buffer, output, continuous=True)
        finally:
            bridge.close()


def guard_supervisor(pid, start_identity):
    """Retire even when native code blocks and the supervisor exits unexpectedly."""
    if sys.platform == 'win32':
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [C.c_uint32, C.c_bool, C.c_uint32]
        kernel.OpenProcess.restype = C.c_void_p
        handle = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)
        if not handle:
            raise RuntimeError('Supervisor process is unavailable')
        kernel.GetProcessTimes.argtypes = [C.c_void_p] + [C.POINTER(C.c_uint64)] * 4
        kernel.GetProcessTimes.restype = C.c_bool
        created, exited, system, user = (C.c_uint64() for _ in range(4))
        if not kernel.GetProcessTimes(handle, C.byref(created), C.byref(exited), C.byref(system), C.byref(user)):
            raise RuntimeError('Cannot verify supervisor process identity')
        if start_identity != f'windows-filetime:{created.value}':
            raise RuntimeError('Supervisor process identity changed')
        kernel.WaitForSingleObject.argtypes = [C.c_void_p, C.c_uint32]
        kernel.WaitForSingleObject.restype = C.c_uint32
        def watch():
            kernel.WaitForSingleObject(handle, 0xffffffff)
            os._exit(98)
    else:
        if os.getppid() != pid:
            raise RuntimeError('Supervisor process identity changed')
        def watch():
            while os.getppid() == pid:
                time.sleep(0.1)
            os._exit(98)
    threading.Thread(target=watch, name='supervisor-watch', daemon=True).start()


if __name__ == '__main__':
    main()

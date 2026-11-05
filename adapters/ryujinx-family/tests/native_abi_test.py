#!/usr/bin/env python3
"""Exercise a built C ABI library over its authenticated actual loopback transport."""
import argparse
import base64
import ctypes as c
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import zlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("eden_native_tests", HERE.parents[1] / "eden-family/tests/run.py")
eden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eden)
Running = c.CFUNCTYPE(c.c_int32, c.c_void_p)
Counter = c.CFUNCTYPE(c.c_uint64, c.c_void_p)
Input = c.CFUNCTYPE(c.c_int32, c.c_void_p, c.c_uint32, *([c.c_int32] * 4))
Touch = c.CFUNCTYPE(c.c_int32, c.c_void_p, c.c_int32, c.c_uint32, c.c_uint32)
Capture = c.CFUNCTYPE(c.c_int32, c.c_void_p, c.c_uint64)
SetRunning = c.CFUNCTYPE(c.c_int32, c.c_void_p, c.c_int32)


def set_native_environment(**values):
    os.environ.update(values)
    if os.name == 'nt':
        # A MinGW DLL's MSVCRT environment table is separate from Python's UCRT
        # table. Update the native view too before testing live getenv admission.
        runtime = c.CDLL('msvcrt')
        runtime._wputenv.argtypes, runtime._wputenv.restype = [c.c_wchar_p], c.c_int
        runtime._wgetenv.argtypes, runtime._wgetenv.restype = [c.c_wchar_p], c.c_wchar_p
        for key, value in values.items():
            assert runtime._wputenv(key + '=' + value) == 0
            assert runtime._wgetenv(key) == value


class Options(c.Structure):
    _fields_ = [("struct_size", c.c_uint32), ("abi_version", c.c_uint32)] + [
        (name, c.c_char_p) for name in ("profile_json", "renderer", "content",
                                      "effective_user_root", "adapter_build", "native_system")]


class Callbacks(c.Structure):
    _fields_ = [("struct_size", c.c_uint32), ("abi_version", c.c_uint32), ("user", c.c_void_p),
               ("running", Running), ("counter", Counter), ("input", Input), ("touch", Touch),
               ("request_capture", Capture), ("set_running", SetRunning)]


def exercise(library):
    dll = c.CDLL(str(Path(library).resolve()))
    dll.emucap_native_abi_version.restype = c.c_uint32
    assert dll.emucap_native_abi_version() == 1
    dll.emucap_native_create.argtypes = [c.POINTER(Options), c.POINTER(Callbacks), c.c_char_p, c.c_size_t]
    dll.emucap_native_create.restype = c.c_void_p
    for name in ("pump", "stop"):
        function = getattr(dll, "emucap_native_" + name)
        function.argtypes = [c.c_void_p, c.c_char_p, c.c_size_t]
        function.restype = c.c_int32
    dll.emucap_native_destroy.argtypes = [c.c_void_p]
    dll.emucap_native_complete_capture.argtypes = [c.c_void_p, c.c_uint64, c.c_uint32, c.c_uint32,
        c.POINTER(c.c_uint8), c.c_size_t, c.c_int32, c.c_int32, c.c_int32, c.c_char_p, c.c_size_t]
    dll.emucap_native_fail_capture.argtypes = [c.c_void_p, c.c_uint64, c.c_char_p, c.c_size_t]
    error = c.create_string_buffer(256)
    with tempfile.TemporaryDirectory(prefix="emucap-ryujinx-abi-") as directory:
        root = Path(directory) / 'utf8-\u00e9-\u65e5'
        root.mkdir()
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0)); listener.listen(1); listener.settimeout(5)
        port = listener.getsockname()[1]
        key, runtime = "front-direct-" + "a" * 64, "launch-" + "0" * 26
        profile = dict(schema="emucap-emulator-build/v1", family="ryujinx-family", bridge_api=1,
                       fork="fixture", revision="a" * 40, systems=["switch"], renderers=["vulkan"])
        profile_path = root / "profile.json"; profile_path.write_text(json.dumps(profile))
        set_native_environment(EMUCAP_PORT=str(port), EMUCAP_SESSION_TOKEN=key, EMUCAP_LAUNCH_ID=runtime,
            EMUCAP_SYSTEM="switch", EMUCAP_RENDERER="vulkan", EMUCAP_USER_ROOT=str(root),
            EMUCAP_BUILD_PROFILE=str(profile_path))
        state = dict(buttons=0, axes=None, touch=None, running=True, capture=0, count=0,
                     mode="rgba", effect_success=1)
        def input_callback(_, buttons, *axes):
            if state["effect_success"]: state.update(buttons=buttons, axes=axes)
            return state["effect_success"]
        def touch_callback(_, active, x, y):
            state["touch"] = (x, y) if active else None
            return 1
        def set_running(_, running):
            state["running"] = bool(running)
            return 1
        def capture_callback(_, identifier):
            state["capture"] = identifier
            if state["mode"] == "pending": return 1
            if state["mode"] == "fail":
                assert dll.emucap_native_fail_capture(handle, identifier, error, len(error))
                return 1
            if state["mode"] == "large":
                pixels = (c.c_uint8 * (1920 * 1080 * 4))()
                assert dll.emucap_native_complete_capture(handle, identifier, 1920, 1080, pixels,
                    len(pixels), 0, 0, 0, error, len(error)), error.value
                return 1
            # Logical 2x2 RGBA: red, green / blue, white. Both axes flipped in storage.
            rgba = bytes([255,255,255,255, 0,0,255,255, 0,255,0,255, 255,0,0,255])
            bgra = state["mode"] == "bgra"
            data = bytearray(rgba)
            if bgra:
                for i in range(0, len(data), 4): data[i], data[i+2] = data[i+2], data[i]
            pixels = (c.c_uint8 * len(data)).from_buffer_copy(data)
            assert not dll.emucap_native_complete_capture(handle, identifier, 1921, 2, pixels,
                len(data), bgra, 1, 1, error, len(error))
            assert dll.emucap_native_complete_capture(handle, identifier, 2, 2, pixels,
                len(data), bgra, 1, 1, error, len(error)), error.value
            return 1
        callbacks = Callbacks(c.sizeof(Callbacks), 1, None, Running(lambda _: state["running"]),
            Counter(lambda _: state["count"]), Input(input_callback), Touch(touch_callback),
            Capture(capture_callback), SetRunning(set_running))
        options = Options(c.sizeof(Options), 1, json.dumps(profile).encode(), b"vulkan", b"homebrew.nro",
                          str(root).encode(), b"fixture-build", b"switch")
        options.abi_version = 2
        assert not dll.emucap_native_create(c.byref(options), c.byref(callbacks), error, len(error))
        assert b"ABI" in error.value
        options.abi_version = 1
        for wrong in (dict(profile, family="eden-family"), dict(profile, bridge_api=2)):
            profile_path.write_text(json.dumps(wrong))
            assert not dll.emucap_native_create(c.byref(options), c.byref(callbacks), error, len(error))
        # Matching sidecar/compiled inputs must still fail family/API admission itself.
        for wrong in (dict(profile, family="eden-family"), dict(profile, bridge_api=2)):
            profile_path.write_text(json.dumps(wrong))
            options.profile_json = json.dumps(wrong).encode()
            assert not dll.emucap_native_create(c.byref(options), c.byref(callbacks), error, len(error))
            assert b"environment/build mismatch" in error.value, error.value
        options.profile_json = json.dumps(profile).encode()
        profile_path.write_text(json.dumps(profile))
        set_native_environment(EMUCAP_SYSTEM="switch2")
        assert not dll.emucap_native_create(c.byref(options), c.byref(callbacks), error, len(error))
        set_native_environment(EMUCAP_SYSTEM="switch")
        handle = dll.emucap_native_create(c.byref(options), c.byref(callbacks), error, len(error))
        assert handle, error.value
        stop = threading.Event()
        owner_errors = []
        def owner():
            try:
                while not stop.is_set():
                    state["count"] += int(state["running"])
                    assert dll.emucap_native_pump(handle, error, len(error)), error.value
                    time.sleep(.005)
                assert dll.emucap_native_stop(handle, error, len(error)), error.value
            except BaseException as exception: owner_errors.append(exception)
        worker = threading.Thread(target=owner); worker.start()
        sock = None
        try:
            sock, _ = listener.accept(); sock.settimeout(5)
            eden.authenticate(sock, port, key, runtime)
            stream = sock.makefile("rb")
            sequence = 0
            def send(method, params=None):
                nonlocal sequence
                sequence += 1
                sock.sendall((json.dumps(dict(v=1,id=sequence,method=method,params=params or {}))+"\n").encode())
                return sequence
            def terminal(identifier):
                while True:
                    line = stream.readline(8*1024*1024+1)
                    assert len(line) <= 8*1024*1024, "native response exceeds wire limit"
                    response = json.loads(line)
                    assert response["id"] == identifier, response
                    if response.get("result", {}).get("status") != "working": return response
            def call(method, params=None): return terminal(send(method, params))
            hello = call("hello")["result"]
            assert hello["adapter"] == "ryujinx-family-native"
            assert hello["host_build"]["family"] == "ryujinx-family"
            assert hello["contracts"]["active_exceptions"] == ["ryujinx.input-touch.persistent-only"]
            assert hello["input_buttons"] == list(("a b x y lstick rstick l r zl zr plus minus left up right down sl sr").split())
            assert "pause" in hello["methods"] and "resume" in hello["methods"] and "step" not in hello["methods"]
            assert hello["touch_capability"]["bounds"] == dict(x_min=0,x_max=1279,y_min=0,y_max=719)
            assert call("set_input", dict(buttons=["a"], axes=dict(stick_x=-32767,cstick_y=32767)))["ok"]
            held = state["buttons"], state["axes"]
            assert held == (1, (-32767,0,0,32767))
            for button in ("home", "capture"):
                assert not call("set_input", dict(buttons=[button]))["ok"]
                assert (state["buttons"], state["axes"]) == held
            state["effect_success"] = 0
            assert not call("set_input", dict(buttons=[]))["ok"]
            assert (state["buttons"], state["axes"]) == held
            state["effect_success"] = 1
            for point in ((0,0),(1279,719)):
                assert call("touch", dict(x=point[0],y=point[1]))["ok"]
                assert state["touch"] == point
            assert not call("touch",dict(x=1280,y=719))["ok"]
            assert state["touch"] == (1279,719)
            for mode in ("rgba", "bgra"):
                state["mode"] = mode
                image = call("screenshot")["result"]
                assert (image["width"],image["height"]) == (2,2)
                png = base64.b64decode(image["png_base64"])
                offset, compressed = 8, b""
                while offset < len(png):
                    length = struct.unpack(">I",png[offset:offset+4])[0]
                    if png[offset+4:offset+8] == b"IDAT": compressed += png[offset+8:offset+8+length]
                    offset += length+12
                assert zlib.decompress(compressed) == bytes([0,255,0,0,0,255,0,0,0,0,255,255,255,255])
            state["mode"] = "large"
            large = call("screenshot")["result"]
            assert (large["width"], large["height"]) == (1920,1080)
            assert len(base64.b64decode(large["png_base64"])) <= ((8*1024*1024-65536)*3//4)
            assert call("status")["ok"]
            state["mode"] = "fail"
            failed = call("screenshot")
            assert not failed["ok"] and failed["error"]["kind"] == "capture_failed"
            assert not call("pause", {"cpu": "arm9"})["ok"] and state["running"]
            assert call("pause")["ok"] and not state["running"]
            assert not call("screenshot")["result"]["fresh"]
            assert not call("resume", {"cpu": "arm9"})["ok"] and not state["running"]
            assert call("resume")["ok"] and state["running"]
            state["mode"] = "pending"
            previous = state["capture"]
            send("screenshot")
            deadline = time.monotonic()+2
            while state["capture"] == previous and time.monotonic()<deadline: time.sleep(.01)
            assert state["capture"] != previous, 'pending capture was not admitted before stop'
            stop.set(); worker.join(5); assert not worker.is_alive()
            assert not owner_errors, owner_errors
            assert state["buttons"] == 0 and state["touch"] is None
            assert not dll.emucap_native_complete_capture(handle,state["capture"],2,2,None,16,0,0,0,error,len(error))
            assert b"no longer pending" in error.value
            assert not dll.emucap_native_fail_capture(handle,state["capture"],error,len(error))
            stream.close()
        finally:
            stop.set(); worker.join(5)
            if sock: sock.close()
            listener.close()
            dll.emucap_native_destroy(handle)
        assert not owner_errors, owner_errors
    print("C ABI authenticated identity/input/touch/capture/pause/stop checks passed (synthetic hooks).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library")
    exercise(parser.parse_args().library)

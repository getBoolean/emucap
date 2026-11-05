"""Software-only melonDS DS / mGBA worker using the supervised libretro ABI loop.

The desktop applications are separate from these headless core builds. A pinned
source build exports its profile; the Rust supervisor validates it before launch.
"""
import ctypes as C
import importlib.util
import json
import pathlib

_path = pathlib.Path(__file__).resolve().parents[1] / 'azahar' / 'bridge.py'
_spec = importlib.util.spec_from_file_location('emucap_libretro_abi', _path)
abi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(abi)


class Bridge(abi.Bridge):
    adapter = 'software-libretro'
    axes_names = ()

    def __init__(self, core, rom, directory, profile=None):
        selected = pathlib.Path(profile) if profile else pathlib.Path(core).parent / 'emucap-emulator-build.json'
        with selected.open('rb') as source:
            raw = source.read(128 * 1024 + 1)
        if len(raw) > 128 * 1024:
            raise ValueError('Build profile exceeds bound')
        self.configure(json.loads(raw))
        super().__init__(core, rom, directory, profile)

    def configure(self, profile):
        if profile.get('family') != 'software-libretro':
            raise ValueError('Expected software-libretro build profile')
        if profile.get('fork') == 'mgba' and profile.get('systems') == ['gba']:
            self.system, self.initial_geometry, self.touch_size = 'gba', (240, 160), None
            self.buttons_map = {name: abi.BUTTONS[name] for name in
                                'a b select start up down left right l r'.split()}
            self.options = {b'mgba_skip_bios': b'ON', b'mgba_use_bios': b'OFF',
                            b'mgba_frameskip': b'disabled', b'mgba_color_correction': b'OFF',
                            b'mgba_interframe_blending': b'OFF'}
        elif profile.get('fork') == 'melonds' and profile.get('systems') == ['nds']:
            self.system, self.initial_geometry, self.touch_size = 'nds', (256, 384), (256, 192)
            self.buttons_map = {name: abi.BUTTONS[name] for name in
                                'a b x y select start up down left right l r'.split()}
            self.options = {b'melonds_render_mode': b'software', b'melonds_screen_layout1': b'top-bottom',
                            b'melonds_number_of_screen_layouts': b'one', b'melonds_screen_gap': b'0',
                            b'melonds_touch_mode': b'touch', b'melonds_console_mode': b'ds',
                            b'melonds_jit_enable': b'disabled', b'melonds_boot_mode': b'direct', b'melonds_sysfile_mode': b'builtin'}
        else:
            raise ValueError('Unsupported core/system selection')

    def input(self, port, device, index, key):
        if port != 0:
            return 0
        if device == 6 and index == 0 and self.system == 'nds' and self.touch is not None:
            x, y = self.touch
            # libretro pointer spans the complete pinned top/bottom composite.
            return (round((x + 0.5) * 65534 / 256 - 32767),
                    round((y + 192.5) * 65534 / 384 - 32767), 1)[key] if key < 3 else 0
        if device == 1 and key == 256:
            return sum(1 << button for button in self.buttons)
        return super().input(port, device, index, key)

    def environment(self, cmd, data):
        if cmd == 51:  # RETRO_ENVIRONMENT_GET_INPUT_BITMASKS (no data argument)
            return True
        if cmd == 32 and data:  # SET_SYSTEM_AV_INFO
            self.set_geometry(C.cast(data, C.POINTER(abi.AvInfo)).contents.geometry)
            return True
        return super().environment(cmd, data)


if __name__ == '__main__':
    abi.main(Bridge)

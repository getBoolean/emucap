"""Independent Input Lab image decoder and full-state oracle (Pillow required)."""
import struct
import zlib


def require_handheld_ui(path, width):
    """Require visible title and sample labels, independently of telemetry validity."""
    from PIL import Image
    with Image.open(path) as source:
        image = source.convert('RGB')
    scale = image.width // width
    cyan = sum(1 for y in range(7, 12) for x in range(8, 44)
               if 40 <= image.getpixel((x*scale, y*scale))[0] <= 180
               and min(image.getpixel((x*scale, y*scale))[1:]) >= 180)
    labels = sum(1 for y in range(16, 21) for x in range(8, 60)
                 if min(image.getpixel((x*scale, y*scale))) >= 150)
    if cyan < 15 or labels < 15:
        raise ValueError('Handheld viewer title/sample labels are missing')


def decode(path, width, height, *, target=None, build_id=None):
    from PIL import Image
    with Image.open(path) as source:
        image = source.convert('RGB')
    if image.width % width or image.width < width or image.height < height * (image.width // width):
        raise ValueError(f'capture does not contain integer-scaled {width}x{height} primary screen')
    scale = image.width // width
    words = [0] * 32
    for bit in range(1024):
        x, y = (8 + bit % 64 * 2 + 1) * scale, (height - 40 + bit // 64 * 2 + 1) * scale
        rgb = image.getpixel((x, y))
        if min(rgb) >= 224:
            words[bit // 32] |= 1 << (bit % 32)
        elif max(rgb) > 32:
            raise ValueError(f'non-monochrome record cell: {rgb}')
    if words[:2] != [0x494c4142, 1]:
        raise ValueError('Input Lab magic/version missing')
    if words[31] != zlib.crc32(struct.pack('<31I', *words[:31])):
        raise ValueError('Input Lab checksum mismatch')
    if words[19] != width | height << 16:
        raise ValueError('native framebuffer identity mismatch')
    if target is not None and words[2] != target:
        raise ValueError(f'wrong guest target: {words[2]}, expected {target}')
    if any(words[29:31]) or words[24] not in (0, 1, 2):
        raise ValueError('unsupported record fields')
    identity = struct.pack('<4I', *words[25:29]).hex()
    if build_id is not None and identity != build_id:
        raise ValueError('guest build identity mismatch')
    signed = lambda value: value - 65536 if value >= 32768 else value
    pair = lambda value: [value & 65535, value >> 16]
    wide = lambda i: words[i] | words[i + 1] << 32
    return {'target': words[2], 'sequence': words[3], 'buttons': wide(4),
            'native_buttons': wide(6), 'axes': [signed(x) for i in (8, 9) for x in pair(words[i])],
            'triggers': pair(words[10]), 'touch': None if words[11] == 0xffffffff else pair(words[11]),
            'valid': words[12], 'port': words[13], 'pressed_seen': wide(14),
            'released_seen': wide(16), 'transitions': words[18], 'screen': pair(words[19]),
            'touch_screen': pair(words[20]), 'left_max': words[21], 'right_max': words[22],
            'trigger_max': words[23], 'y_direction': words[24], 'build_id': identity}


def require_state(observed, expected, *, after, axis_tolerance=0):
    delta = (observed['sequence'] - after) & 0xffffffff
    if not 0 < delta < 0x80000000:
        raise AssertionError(f'stale guest sample: {after} -> {observed["sequence"]}')
    if not observed['valid'] & 1:
        raise AssertionError('guest controller disconnected')
    for field in ('buttons', 'port', 'touch', 'triggers'):
        if field in expected and observed[field] != expected[field]:
            raise AssertionError(f'{field}: expected {expected[field]}, observed {observed[field]}')
    if 'axes' in expected and (len(expected['axes']) != 4 or
            any(abs(a - b) > axis_tolerance for a, b in zip(observed['axes'], expected['axes']))):
        raise AssertionError(f'axes: expected {expected["axes"]}, observed {observed["axes"]}')

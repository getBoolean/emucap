"""Rasterize the credited input-viewer base; resvg-py 0.5.0 and Pillow required."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path


def generate(output):
    import resvg_py
    from PIL import Image
    assets = Path(__file__).resolve().parents[2] / 'docs/design/assets/procon'
    provenance = json.loads((assets / 'provenance.json').read_text(encoding='utf-8'))
    base = next(entry for entry in provenance['files'] if entry['local_path'] == 'base.svg')
    if hashlib.sha256((assets / 'base.svg').read_bytes()).hexdigest() != base['sha256']:
        raise ValueError('controller artwork differs from its retained provenance')
    raw = resvg_py.svg_to_bytes(svg_path=str(assets / 'base.svg'), width=330, height=251,
                               background='#101d30', skip_system_fonts=True)
    image = Image.open(BytesIO(raw)).convert('RGB')
    words = [(r >> 3) << 11 | (g >> 2) << 5 | b >> 3 for r, g, b in image.getdata()]
    output.mkdir(parents=True, exist_ok=True)
    (output / 'controller_art.h').write_text(
        '/* Derived from the credited Open Joystick Display / shmove base.svg.\n'
        ' * See CONTROLLER-COPYRIGHT.md in this artifact directory. */\n'
        '#define LAB_ART_WIDTH 330\n#define LAB_ART_HEIGHT 251\n'
        'static const uint16_t lab_controller_art[]={\n' +
        ',\n'.join(','.join(hex(v) for v in words[i:i+24]) for i in range(0, len(words), 24)) +
        '\n};\n', encoding='utf-8')
    (output / 'controller.png').write_bytes(raw)
    (output / 'CONTROLLER-COPYRIGHT.md').write_bytes((assets / 'COPYRIGHT.md').read_bytes())
    (output / 'CONTROLLER-PROVENANCE.json').write_text(json.dumps({
        'upstream': provenance, 'transform': 'resvg-py 0.5.0, 330x251 RGB565, navy background',
        'input_sha256': hashlib.sha256((assets / 'base.svg').read_bytes()).hexdigest(),
        'acknowledgement': 'This product includes software developed by "Open Joystick Display '
            'Project and \'Anthony Mattera\' (http://www.ojdproject.com/)."'}, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    generate(parser.parse_args().output)

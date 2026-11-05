"""Build unsigned Ounce homebrew metadata with a pinned npdmtool format extension."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

REVISION = '22756068dd0ed6ff9734c59cb4f99ebd3f62555b'


def validate(data):
    if len(data) < 0x80 or data[:4] != b'META':
        raise ValueError('invalid META header')
    aci, aci_size, acid, acid_size = struct.unpack_from('<4I', data, 0x70)
    for offset, size, minimum in ((aci, aci_size, 0x40), (acid, acid_size, 0x340)):
        if offset < 0x80 or offset % 16 or size < minimum or offset + size > len(data):
            raise ValueError('invalid metadata section bounds')
    if not (acid + acid_size <= aci or aci + aci_size <= acid):
        raise ValueError('metadata sections overlap')
    if data[acid + 0x300:acid + 0x304] != b'ACID':
        raise ValueError('missing Ounce ACID magic at signature/key offset 0x300')
    if data[aci:aci + 4] != b'ACI0':
        raise ValueError('missing ACI0 magic')
    if struct.unpack_from('<I', data, acid + 0x304)[0] != acid_size - 0x180:
        raise ValueError('ACID signed-data size mismatch')
    for section_size, header, descriptors in (
            (acid_size, 0x340, acid + 0x320), (aci_size, 0x40, aci + 0x20)):
        intervals = []
        for position in range(descriptors, descriptors + 24, 8):
            offset, size = struct.unpack_from('<2I', data, position)
            if offset < header or offset + size > section_size:
                raise ValueError('access descriptor outside its section')
            if size:
                intervals.append((offset, offset + size))
        ordered = sorted(intervals)
        if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
            raise ValueError('access descriptors overlap')
    program_id = struct.unpack_from('<Q', data, aci + 0x10)[0]
    low, high = struct.unpack_from('<2Q', data, acid + 0x310)
    if not low <= program_id <= high:
        raise ValueError('program identity outside permitted range')
    return {'platform': 'ounce', 'program_id': f'{program_id:016x}',
            'acid_offset': acid, 'acid_size': acid_size, 'aci_offset': aci, 'aci_size': aci_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--switch-tools-source', type=Path, required=True)
    parser.add_argument('--cc', required=True)
    parser.add_argument('--descriptor', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.switch_tools_source.resolve()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if revision != REVISION or subprocess.check_output(['git', 'diff', 'HEAD', '--', 'src/npdmtool.c', 'src/cJSON.c', 'src/cJSON.h'], cwd=source):
        raise ValueError('requires unchanged pinned switch-tools source')
    descriptor = json.loads(args.descriptor.read_text(encoding='utf-8'))
    if descriptor.get('platform') != 'ounce':
        raise ValueError('dedicated Ounce generator requires platform: ounce')
    text = (source / 'src/npdmtool.c').read_text(encoding='utf-8')
    for before, after in [('u8 Signature[0x100];', 'u8 Signature[0x180];'),
                          ('u8 Modulus[0x100];', 'u8 Modulus[0x180];'),
                          ('sizeof(NpdmAcid) != 0x240', 'sizeof(NpdmAcid) != 0x340')]:
        if text.count(before) != 1:
            raise ValueError('pinned npdmtool layout changed')
        text = text.replace(before, after)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='emucap-npdmtool-ounce-') as temporary:
        temporary = Path(temporary)
        modified = temporary / 'npdmtool.c'
        modified.write_text(text, encoding='utf-8')
        binary = temporary / ('npdmtool-ounce.exe' if os.name == 'nt' else 'npdmtool-ounce')
        subprocess.run([args.cc, '-O2', '-I' + str(source / 'src'), str(modified),
                        str(source / 'src/cJSON.c'), '-lm', '-o', str(binary)], check=True, timeout=120)
        subprocess.run([str(binary), str(args.descriptor.resolve()), str(output)], check=True, timeout=15)
    data = output.read_bytes()
    facts = validate(data)
    facts.update(source_revision=revision, unsigned_homebrew=True,
                 generator='switchbrew npdmtool with emucap Ounce-only signature/modulus sizing extension',
                 sha256=hashlib.sha256(data).hexdigest(),
                 descriptor_sha256=hashlib.sha256(args.descriptor.read_bytes()).hexdigest())
    print(json.dumps(facts, indent=2))


if __name__ == '__main__':
    main()

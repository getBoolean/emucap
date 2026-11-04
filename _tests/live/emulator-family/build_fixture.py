#!/usr/bin/env python3
"""Build original, key-free homebrew with an existing devkitPro installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--devkitpro', required=True, type=Path)
    parser.add_argument('--system', required=True, choices=['3ds', 'switch'])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = args.devkitpro.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    suffix = '.exe' if os.name == 'nt' else ''
    ctr = args.system == '3ds'
    kit = root / ('devkitARM' if ctr else 'devkitA64')
    compiler = kit / 'bin' / (('arm-none-eabi-gcc' if ctr else 'aarch64-none-elf-gcc') + suffix)
    library = root / ('libctru' if ctr else 'libnx')
    source = Path(__file__).with_name('ctr.c' if ctr else 'switch.c')
    elf = out / 'witness.elf'
    flags = (['-march=armv6k', '-mtune=mpcore', '-mfloat-abi=hard', '-mtp=soft',
              '-mword-relocations', '-D__3DS__', '-specs=' + str(kit / 'arm-none-eabi/lib/3dsx.specs')]
             if ctr else ['-march=armv8-a+crc+crypto', '-mtune=cortex-a57', '-mtp=soft',
                          '-fPIE', '-D__SWITCH__', '-specs=' + str(library / 'switch.specs')])
    command = [str(compiler), '-O2', '-Wall', '-Wextra', '-Werror', '-ffunction-sections',
               *flags, '-I' + str(library / 'include'), str(source),
               '-L' + str(library / 'lib'), '-lctru' if ctr else '-lnx', '-lm', '-o', str(elf)]
    environment = dict(os.environ, DEVKITPRO=root.as_posix())
    subprocess.run(command, check=True, timeout=120, env=environment)
    fixture = out / ('witness.3dsx' if ctr else 'witness.nro')
    pack = root / 'tools/bin' / (('3dsxtool' if ctr else 'elf2nro') + suffix)
    subprocess.run([str(pack), str(elf), str(fixture)], check=True, timeout=30)
    manifest = {'system': args.system, 'content': fixture.name, 'license': 'CC0-1.0',
                'source': source.name, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
                'compiler': subprocess.check_output([str(compiler), '--version'], text=True).splitlines()[0],
                'command': command, 'qualification': 'fixture-build-only; no emulator execution'}
    (out / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (out / 'fixture.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(fixture)


if __name__ == '__main__':
    main()

"""Cross-build original Input Lab ports with an explicitly selected local devkitPro."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys

HERE = Path(__file__).resolve().parent
FAMILY = HERE.parent / 'live/emulator-family'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--devkitpro', type=Path, required=True)
    parser.add_argument('--system', choices=['switch', '3ds', 'nds', 'gba', 'gamecube', 'wii', 'switch2'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--art', type=Path, required=True, help='Output directory from make_art.py')
    parser.add_argument('--libnx-ounce-source', type=Path)
    parser.add_argument('--libnx-ounce-library-sha256')
    parser.add_argument('--switch-tools-source', type=Path)
    parser.add_argument('--cc', help='Host compiler for reviewed Ounce npdmtool')
    args = parser.parse_args()
    if args.system == 'switch2' and not all((args.libnx_ounce_source,
            args.libnx_ounce_library_sha256, args.switch_tools_source, args.cc)):
        parser.error('Switch 2 needs pinned libnx-ounce source/hash, switch-tools source and --cc')
    root, out, art = args.devkitpro.resolve(), args.output.resolve(), args.art.resolve()
    for name in ('controller_art.h', 'CONTROLLER-COPYRIGHT.md', 'CONTROLLER-PROVENANCE.json'):
        if not (art / name).is_file():
            parser.error(f'missing generated artwork file: {art / name}')
    out.mkdir(parents=True, exist_ok=False)
    suffix = '.exe' if os.name == 'nt' else ''
    system = args.system
    arm = system in ('3ds', 'nds', 'gba')
    ppc = system in ('gamecube', 'wii')
    kit = root / ('devkitARM' if arm else 'devkitPPC' if ppc else 'devkitA64')
    prefix = 'arm-none-eabi-' if arm else 'powerpc-eabi-' if ppc else 'aarch64-none-elf-'
    compiler = kit / 'bin' / (prefix + 'gcc' + suffix)
    tools = root / 'tools/bin'
    elf = out / 'input-lab.elf'
    source = HERE / ('ctr.c' if system == '3ds' else 'handheld.c' if system in ('nds', 'gba')
                     else 'ogc.c' if ppc else 'switch.c')
    environment = dict(os.environ, DEVKITPRO=root.as_posix())
    includes = [HERE, art]
    flags = []
    libraries = []
    library_paths = []
    manifest_extra = {}
    if system == '3ds':
        flags = ['-march=armv6k', '-mtune=mpcore', '-mfloat-abi=hard', '-mtp=soft',
                 '-mword-relocations', '-D__3DS__', '-specs=' + str(kit / 'arm-none-eabi/lib/3dsx.specs')]
        library = root / 'libctru'
        libraries = ['ctru', 'm']
    elif system == 'nds':
        flags = ['-march=armv5te', '-mtune=arm946e-s', '-mthumb', '-DARM9', '-D__NDS__',
                 '-specs=' + str(root / 'calico/share/ds9.specs')]
        library = root / 'libnds'
        includes.append(root / 'calico/include')
        library_paths.append(root / 'calico/lib')
        libraries = ['nds9', 'calico_ds9', 'm']
    elif system == 'gba':
        flags = ['-mthumb', '-mthumb-interwork', '-mcpu=arm7tdmi', '-specs=gba.specs']
        library = root / 'libgba'
        libraries = ['gba', 'm']
    elif ppc:
        flags = ['-DGEKKO', '-mrvl' if system == 'wii' else '-mogc', '-mcpu=750', '-meabi', '-mhard-float']
        if system == 'wii':
            flags.append('-DHW_RVL')
        library = root / 'libogc'
        library_paths.append(library / 'lib' / ('wii' if system == 'wii' else 'cube'))
        libraries = (['wiiuse', 'bte'] if system == 'wii' else []) + ['ogc', 'm']
    else:
        library = root / 'libnx'
        flags = ['-march=armv8-a+crc+crypto', '-mtune=cortex-a57', '-mtp=soft', '-fPIE', '-D__SWITCH__']
        if system == 'switch2':
            sys.path.insert(0, str(FAMILY))
            from build_ounce_fixture import checked_library, LIBOUNCE_REVISION
            digest = checked_library(args.libnx_ounce_source.resolve(), args.libnx_ounce_library_sha256)
            library = args.libnx_ounce_source.resolve() / 'nx'
            flags[:2] = ['-march=armv8.2-a+crc+crypto+pauth', '-mtune=cortex-a78c']
            flags.append('-D__SWITCH2__')
            sdk = out / 'sdk/libounce'
            sdk.mkdir(parents=True)
            shutil.copy2(library / 'switch.ld', sdk / 'switch.ld')
            environment['DEVKITPRO'] = (out / 'sdk').as_posix()
            includes.append(library / 'external/bsd/include')
            manifest_extra = {'libnx_ounce_revision': LIBOUNCE_REVISION, 'libnx_ounce_library_sha256': digest}
        flags.append('-specs=' + str(library / 'switch.specs'))
        libraries = ['nx', 'm']
    includes.append(library / 'include')
    library_paths.append(library / 'lib')
    if system not in ('gba', 'nds'):
        flags.append('-DLAB_ARTWORK')
    source_files = (source, HERE / 'lab.h', art / 'controller_art.h')
    identity = hashlib.sha256(system.encode() + b''.join(p.read_bytes() for p in source_files)).digest()[:16]
    flags.extend(f'-DLAB_BUILD_ID{i}=0x{value:08x}u' for i, value in enumerate(struct.unpack('<4I', identity)))
    command = [str(compiler), '-O2', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
               '-ffunction-sections', '-fdata-sections', *flags,
               *['-I' + str(p) for p in includes], str(source),
               *['-L' + str(p) for p in library_paths], *['-l' + lib for lib in libraries], '-o', str(elf)]
    commands = [command]

    def run(command):
        commands.append(command)
        subprocess.run(command, env=environment, check=True, timeout=150)

    subprocess.run(command, env=environment, check=True, timeout=150)
    if system in ('switch', '3ds'):
        content = out / ('input-lab.3dsx' if system == '3ds' else 'input-lab.nro')
        packaging = [str(tools / (('3dsxtool' if system == '3ds' else 'elf2nro') + suffix)), str(elf), str(content)]
        if system == 'switch':
            nacp = out / 'input-lab.nacp'
            run([str(tools / ('nacptool' + suffix)), '--create', 'Input Lab', 'emucap', '1.0', str(nacp)])
            packaging.append('--nacp=' + str(nacp))
        run(packaging)
    elif system == 'nds':
        content = out / 'input-lab.nds'
        run([str(tools / ('ndstool' + suffix)), '-c', str(content), '-9', str(elf),
             '-7', str(root / 'calico/bin/ds7_maine.elf')])
    elif system == 'gba':
        content = out / 'input-lab.gba'
        run([str(kit / 'bin' / (prefix + 'objcopy' + suffix)), '-O', 'binary', str(elf), str(content)])
        run([str(tools / ('gbafix' + suffix)), str(content), '-tINPUTLAB', '-cILAB', '-m00'])
    elif ppc:
        content = out / 'input-lab.dol'
        run([str(tools / ('elf2dol' + suffix)), str(elf), str(content)])
    else:
        exefs = out / 'exefs'
        exefs.mkdir()
        content = exefs / 'main'
        run([str(tools / ('elf2nso' + suffix)), str(elf), str(content)])
        run([sys.executable, str(FAMILY / 'ounce_npdm.py'), '--switch-tools-source',
             str(args.switch_tools_source.resolve()), '--cc', args.cc,
             '--descriptor', str(FAMILY / 'ounce-witness.npdm.json'), '--output', str(exefs / 'main.npdm')])
        (out / 'emulator.ini').write_text('[Core]\nmemory_layout_mode=4\nmemory_layout_mode\\default=false\n', encoding='utf-8')
        shutil.copy2(args.libnx_ounce_source / 'LICENSE.md', out / 'LIBOUNCE-LICENSE.md')
    for name in ('CONTROLLER-COPYRIGHT.md', 'CONTROLLER-PROVENANCE.json'):
        shutil.copy2(art / name, out / name)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {'system': system, 'content': content.relative_to(out).as_posix(),
                'source_license': 'CC0-1.0 (original Input Lab code only)',
                'artwork_notice': 'CONTROLLER-COPYRIGHT.md',
                'sources': {p.name: sha(p) for p in source_files}, 'build_id': identity.hex(),
                'content_sha256': sha(content), 'commands': commands,
                'compiler': subprocess.check_output([str(compiler), '--version'], text=True).splitlines()[0],
                'qualification': 'cross-build only; no live input or hardware proof', **manifest_extra}
    if system == 'switch2':
        manifest['members'] = {p.name: sha(p) for p in sorted((out / 'exefs').iterdir())}
    (out / 'fixture.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(content)


if __name__ == '__main__':
    main()

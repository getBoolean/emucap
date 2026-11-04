"""Build the original CC0 witness against pinned libounce, without installing an SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

LIBOUNCE_REVISION = 'a04b88b3d3ed059963200d0a3d460754b2fe294e'


def checked_library(source, expected_sha256):
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if (revision != LIBOUNCE_REVISION or
            subprocess.check_output(['git', 'diff', 'HEAD', '--', 'nx'], cwd=source) or
            subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', 'nx'], cwd=source)):
        raise ValueError('requires unchanged pinned libnx-ounce source without untracked nx files')
    digest = hashlib.sha256((source / 'nx/lib/libnx.a').read_bytes()).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError('libnx-ounce archive differs from expected qualified build hash')
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('devkitpro', 'libnx-ounce-source', 'switch-tools-source', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--cc', required=True, help='Host C compiler for npdmtool')
    parser.add_argument('--libnx-ounce-library-sha256', required=True,
                        help='Expected libnx.a SHA-256 from the reviewed pinned-source library build')
    args = parser.parse_args()
    root, library_source = args.devkitpro.resolve(), args.libnx_ounce_source.resolve()
    library_sha256 = checked_library(library_source, args.libnx_ounce_library_sha256)
    library = library_source / 'nx'
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    exefs = out / 'exefs'
    exefs.mkdir()
    config = out / 'emulator.ini'
    config.write_text('[Core]\nmemory_layout_mode=4\nmemory_layout_mode\\default=false\n', encoding='utf-8')
    sdk = out / 'sdk/libounce'
    sdk.mkdir(parents=True)
    shutil.copy2(library / 'switch.ld', sdk / 'switch.ld')
    source = Path(__file__).with_name('switch.c')
    suffix = '.exe' if os.name == 'nt' else ''
    compiler = root / ('devkitA64/bin/aarch64-none-elf-gcc' + suffix)
    elf = out / 'witness.elf'
    command = [str(compiler), '-O2', '-Wall', '-Wextra', '-Werror', '-ffunction-sections',
               '-march=armv8.2-a+crc+crypto+pauth', '-mtune=cortex-a78c', '-mtp=soft', '-fPIE',
               '-D__SWITCH__', '-D__SWITCH2__', '-specs=' + str(library / 'switch.specs'),
               '-I' + str(library / 'include'), '-I' + str(library / 'external/bsd/include'),
               str(source), '-L' + str(library / 'lib'), '-lnx', '-lm', '-o', str(elf)]
    subprocess.run(command, env=dict(os.environ, DEVKITPRO=(out / 'sdk').as_posix()), check=True, timeout=120)
    subprocess.run([str(root / ('tools/bin/elf2nso' + suffix)), str(elf), str(exefs / 'main')], check=True, timeout=30)
    descriptor = Path(__file__).with_name('ounce-witness.npdm.json')
    metadata = subprocess.check_output([sys.executable, str(Path(__file__).with_name('ounce_npdm.py')),
        '--switch-tools-source', str(args.switch_tools_source.resolve()), '--cc', args.cc,
        '--descriptor', str(descriptor), '--output', str(exefs / 'main.npdm')], text=True, timeout=150)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'system': 'switch2', 'content': 'exefs/main', 'source_license': 'CC0-1.0',
        'library_license': 'ISC (libnx authors; see pinned source LICENSE.md)',
        'libnx_ounce_revision': LIBOUNCE_REVISION, 'libnx_ounce_library_sha256': library_sha256,
        'source_sha256': sha(source), 'descriptor_sha256': sha(descriptor),
        'emulator_config_sha256': sha(config), 'heap_bytes': 64 * 1024 * 1024,
        'members': {p.name: sha(p) for p in sorted(exefs.iterdir())},
        'npdm': json.loads(metadata), 'command': command,
        'compiler': subprocess.check_output([str(compiler), '--version'], text=True).splitlines()[0],
        'qualification': 'source-built unsigned homebrew; build only, no live credit'}
    (out / 'fixture.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    shutil.copy2(library_source / 'LICENSE.md', out / 'LIBOUNCE-LICENSE.md')
    print(exefs / 'main')


if __name__ == '__main__':
    main()

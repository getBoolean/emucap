"""Build the pinned, patched software libretro core and its compiled provenance sidecar."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / '_common'))
from build_support import maintained_source


def run(*args, cwd=None, capture=False):
    return subprocess.run([str(arg) for arg in args], cwd=cwd, check=True,
                          stdout=subprocess.PIPE if capture else None,
                          text=capture).stdout


def patch_digest(paths):
    # Framing binds file names and bytes; the generated profile header is deliberately
    # outside the patch set so its embedded digest cannot form a digest cycle.
    digest = hashlib.sha256()
    for path in sorted(paths):
        name, data = path.name.encode(), path.read_bytes()
        digest.update(len(name).to_bytes(4, 'big') + name)
        digest.update(len(data).to_bytes(8, 'big') + data)
    return digest.hexdigest()


def compiler_target(cxx):
    machine = run(cxx, '-dumpmachine', capture=True).strip().lower()
    architecture = machine.split('-')[0]
    architecture = {'arm64': 'aarch64', 'amd64': 'x86_64'}.get(architecture, architecture)
    if architecture not in ('x86_64', 'aarch64'):
        raise RuntimeError(f'Unqualified architecture: {machine}')
    if 'mingw' in machine or 'windows-gnu' in machine:
        return architecture + '-pc-windows-gnu'
    if 'darwin' in machine or 'apple' in machine:
        return architecture + '-apple-darwin'
    if 'linux' in machine:
        return architecture + '-unknown-linux-' + ('musl' if 'musl' in machine else 'gnu')
    raise RuntimeError(f'Unqualified compiler target: {machine}; use native GCC/Clang or MinGW')


def prepare(source, build, cxx):
    lock = maintained_source('azahar')
    if not source.exists():
        source.mkdir(parents=True)
        run('git', 'init', source)
        run('git', 'remote', 'add', 'origin', lock['repository'], cwd=source)
        run('git', 'fetch', '--depth=1', 'origin', lock['revision'], cwd=source)
        run('git', 'checkout', '--detach', lock['revision'], cwd=source)
    if run('git', 'rev-parse', 'HEAD', cwd=source, capture=True).strip() != lock['revision']:
        raise RuntimeError('Source checkout does not match upstream.lock; it was preserved')
    patches = sorted((HERE / 'patches').glob('*.patch'))
    if not patches:
        raise RuntimeError('Native bridge patches are missing')
    if run('git', 'ls-files', '--others', '--exclude-standard', cwd=source, capture=True).strip():
        raise RuntimeError('Source checkout has untracked files; it was preserved')
    diff = subprocess.check_output(['git', 'diff', 'HEAD', '--binary', '--ignore-submodules=all'], cwd=source)
    expected = b''.join(path.read_bytes() for path in patches)
    if not diff:
        for patch in patches:
            run('git', 'apply', '--check', patch, cwd=source)
            run('git', 'apply', patch, cwd=source)
    elif diff != expected:
        raise RuntimeError('Source checkout has edits other than the bridge patches; it was preserved')
    run('git', 'submodule', 'update', '--init', '--recursive', '--jobs', '8', cwd=source)
    run('git', 'submodule', 'foreach', '--recursive', '--quiet',
        'git diff --quiet HEAD && test -z "$(git ls-files --others --exclude-standard)"', cwd=source)
    profile = {'schema': 'emucap-emulator-build/v1', 'family': 'azahar-libretro', 'fork': 'azahar',
               'repository': lock['repository'], 'revision': lock['revision'],
               'patch_sha256': patch_digest(patches), 'bridge_api': lock['bridge_api'],
               'systems': ['3ds'], 'renderers': ['software'], 'cpu_features': [],
               'target': compiler_target(cxx)}
    build.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(profile, separators=(',', ':'), sort_keys=True)
    (build / 'emucap-emulator-build.json').write_text(encoded + '\n', encoding='utf-8')
    (build / 'emucap_profile.h').write_text('#pragma once\n#define EMUCAP_BUILD_PROFILE_JSON ' +
                                          json.dumps(encoded) + '\n', encoding='utf-8')
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--cmake', default='cmake')
    parser.add_argument('--cc', default=os.environ.get('CC', 'gcc' if sys.platform == 'win32' else 'cc'))
    parser.add_argument('--cxx', default=os.environ.get('CXX', 'g++' if sys.platform == 'win32' else 'c++'))
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 256:
        parser.error('--jobs must be 1..256')
    source, build, output = (path.resolve() for path in (args.source_dir, args.build_dir, args.output_dir))
    profile = prepare(source, build, args.cxx)
    if args.prepare_only:
        print(json.dumps(profile, sort_keys=True))
        return
    flags = ['-DENABLE_LIBRETRO=ON', '-DENABLE_OPENGL=OFF', '-DENABLE_VULKAN=OFF',
             '-DENABLE_SOFTWARE_RENDERER=ON', '-DENABLE_TESTS=OFF', '-DENABLE_LTO=OFF',
             '-DENABLE_BUILTIN_KEYBLOB=OFF', '-DENABLE_SSE42=OFF', '-DENABLE_NATIVE_OPTIMIZATION=OFF',
             '-DCITRA_WARNINGS_AS_ERRORS=OFF', '-DCMAKE_BUILD_TYPE=Release']
    run(args.cmake, '-S', source, '-B', build, '-G', 'Ninja',
        '-DCMAKE_C_COMPILER=' + args.cc, '-DCMAKE_CXX_COMPILER=' + args.cxx,
        '-DEMUCAP_PROFILE_HEADER=' + str(build / 'emucap_profile.h'), *flags)
    run(args.cmake, '--build', build, '--target', 'citra_libretro', '--parallel', args.jobs)
    suffix = '.dll' if '-windows-' in profile['target'] else '.dylib' if '-apple-' in profile['target'] else '.so'
    libraries = list((build / 'bin').rglob('azahar_libretro' + suffix))
    if len(libraries) != 1:
        raise RuntimeError(f'Expected exactly one built core, found {len(libraries)}')
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(libraries[0], output / libraries[0].name)
    shutil.copy2(build / 'emucap-emulator-build.json', output / 'emucap-emulator-build.json')
    if '-windows-gnu' in profile['target']:
        # GCC runtime DLLs must travel with the core. Python loads from the core's
        # directory rather than relying on the invoking shell's PATH.
        for name in ('libstdc++-6.dll', 'libgcc_s_seh-1.dll', 'libwinpthread-1.dll'):
            runtime = Path(run(args.cxx, '-print-file-name=' + name, capture=True).strip())
            if not runtime.is_file():
                runtime = Path(shutil.which(args.cxx) or args.cxx).resolve().parent / name
            if not runtime.is_file():
                raise RuntimeError(f'MinGW runtime dependency was not found: {name}')
            shutil.copy2(runtime, output / name)
    print(f'Built core and compiled build profile: {output}')


if __name__ == '__main__':
    main()

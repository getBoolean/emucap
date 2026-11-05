"""Build pinned software libretro cores with embedded emucap build identity.

Requires an existing recursive source checkout and a configured CMake build tree.
This adds a generated translation unit without modifying upstream source files.
"""
import argparse
import hashlib
import json
import pathlib
import platform
import subprocess
import sys

PINS = {
    'mgba': ('https://github.com/mgba-emu/mgba.git', '26b7884bc25a5933960f3cdcd98bac1ae14d42e2', 'gba', 'mgba_libretro'),
    'melonds': ('https://github.com/JesseTG/melonds-ds.git', 'f394adbacb5722ee97c1b37c8064da9a25818310', 'nds', 'melondsds_libretro'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fork', choices=PINS, required=True)
    parser.add_argument('--source', type=pathlib.Path, required=True)
    parser.add_argument('--build', type=pathlib.Path, required=True)
    parser.add_argument('--cmake', default='cmake')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    repository, revision, system, target = PINS[args.fork]
    source, build = args.source.resolve(), args.build.resolve()
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no'], text=True)
    if actual != revision or dirty.strip():
        raise RuntimeError('Build requires the clean pinned source revision')
    machine = {'AMD64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine(), platform.machine())
    profile = dict(schema='emucap-emulator-build/v1', family='software-libretro', fork=args.fork,
                   repository=repository, revision=revision,
                   patch_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                   bridge_api=1, systems=[system], renderers=['software'], cpu_features=[],
                   target=machine + '-' + sys.platform.replace('win32', 'windows'))
    build.mkdir(parents=True, exist_ok=True)
    translation = build / 'emucap-profile.c'
    payload = json.dumps(json.dumps(profile, separators=(',', ':')))
    translation.write_text('#ifdef _WIN32\n#define API __declspec(dllexport)\n#else\n'
                           '#define API __attribute__((visibility("default")))\n#endif\n'
                           f'API const char* emucap_get_build_profile_json(void) {{return {payload};}}\n', encoding='utf-8')
    hook = build / 'emucap-profile.cmake'
    hook.write_text(f'cmake_language(DEFER CALL target_sources {target} PRIVATE "{translation.as_posix()}")\n', encoding='utf-8')
    subprocess.run([args.cmake, '-S', str(source), '-B', str(build),
                    '-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES=' + hook.as_posix()], check=True)
    subprocess.run([args.cmake, '--build', str(build), '--target', target, '--parallel', str(args.jobs)], check=True)
    candidates = [p for p in build.rglob('*') if p.is_file() and
                  p.name in (target + '.dll', target + '.so', target + '.dylib')]
    if len(candidates) != 1:
        raise RuntimeError(f'Expected exactly one core library, found {candidates}')
    library = candidates[0]
    (library.parent / 'emucap-emulator-build.json').write_text(json.dumps(profile, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'library': str(library), 'sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
                      'profile': profile}, indent=2))


if __name__ == '__main__':
    main()

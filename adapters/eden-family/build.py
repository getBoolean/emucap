#!/usr/bin/env python3
"""Build one pinned Eden-family SDL bridge without changing installed profiles."""
import argparse
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent


def run(*args, cwd=None):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def output(*args, cwd=None):
    return subprocess.check_output([str(arg) for arg in args], cwd=cwd, text=True).strip()


def patch_digest(patch):
    files = sorted((HERE / 'native').glob('*')) + [patch]
    files += [HERE.parent / '_common' / name for name in (
        'emucap_front_auth.h', 'emucap_native_failure.h', 'emucap_native_failure.cpp',
        'emucap_atomic_file.h')]
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def verify_applied_patch(source, patch):
    """Compare file bytes with a fresh application, avoiding diff algorithm ambiguity."""
    paths = [line[6:] for line in patch.read_text(encoding='utf-8').splitlines()
             if line.startswith('+++ b/')]
    changed = output('git', 'diff', '--name-only', 'HEAD', cwd=source).splitlines()
    if not paths or len(paths) != len(set(paths)) or set(changed) != set(paths):
        raise RuntimeError('source has edits outside the maintained patch')
    with tempfile.TemporaryDirectory(prefix='emucap-patch-verify-') as temporary:
        baseline = pathlib.Path(temporary)
        for name in paths:
            relative = pathlib.PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise RuntimeError('patch contains an unsafe source path')
            destination = baseline / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=source))
        run('git', 'apply', patch, cwd=baseline)
        for name in paths:
            expected = (baseline / name).read_bytes().replace(b'\r\n', b'\n')
            if (source / name).read_bytes().replace(b'\r\n', b'\n') != expected:
                raise RuntimeError('source has edits beyond the exact maintained patch: ' + name)


def cpu_features_for(target):
    if not target.startswith('x86_64-'):
        return []
    # Upstream src/CMakeLists.txt adds -mcx16 for x86_64 and -msse4.1 for MinGW.
    # clang-cl also requires SSE4.1; no Zen/AVX tuning is selected by this recipe.
    return ['cmpxchg16b', 'sse4.1'] if 'windows' in target else ['cmpxchg16b']


def cache_override(arguments, name):
    values = [match.group(1) for argument in arguments
              if (match := re.fullmatch('-D' + re.escape(name) + r'(?::[^=]+)?=(.*)', argument))]
    return values[-1] if values else None


def windows_openssl_options(target, arguments, source=None, build=None):
    if os.name != 'nt' or not target.endswith('windows-gnu'):
        return []
    perl = cache_override(arguments, 'OPENSSL_CONFIGURE_TOOL') or shutil.which('perl')
    if not perl:
        raise RuntimeError('Windows GNU builds require Perl on PATH or -DOPENSSL_CONFIGURE_TOOL=<perl.exe>')
    try:
        perl_os = output(perl, '-MConfig', '-MLocale::Maketext::Simple', '-e', 'print $Config{osname}')
    except subprocess.CalledProcessError as error:
        raise RuntimeError('selected Perl lacks Locale::Maketext::Simple; use a complete native or MSYS2 Perl') from error
    options = ['-DOPENSSL_CONFIGURE_TOOL=' + perl, '-DOPENSSL_ENABLE_PARALLEL=OFF']
    if perl_os.lower() in ('msys', 'cygwin'):
        make = cache_override(arguments, 'MAKE') or shutil.which('make')
        if not make or not any(kind in output(make, '--version').lower() for kind in ('msys', 'cygwin')):
            raise RuntimeError('MSYS2 Perl requires MSYS2 /usr/bin/make.exe; mingw32-make cannot resolve its generated paths')
        if pathlib.Path(perl).resolve().parent != pathlib.Path(make).resolve().parent:
            raise RuntimeError('MSYS Perl and make must come from the same /usr/bin directory')
        if source is not None and build is not None and source.drive.lower() != build.drive.lower():
            raise RuntimeError('MSYS Perl OpenSSL build requires source and output on the same Windows volume; choose --source/--output together')
        options.append('-DMAKE=' + make)
        print('OpenSSL uses verified MSYS tools:', perl, make, flush=True)
    else:
        print('OpenSSL uses selected native Perl:', perl, flush=True)
    return options


def copy_windows_runtime(build, destination):
    cache = (build / 'CMakeCache.txt').read_text(encoding='utf-8')
    selected = re.search(r'^CMAKE_CXX_COMPILER:[^=]+=(.+)$', cache, re.MULTILINE)
    if not selected:
        raise RuntimeError('CMake did not record the selected C++ compiler')
    compiler = pathlib.Path(selected.group(1).strip())
    # Resolve against the selected compiler, even when PATH contains an older GCC.
    for name in ('libstdc++-6.dll', 'libgcc_s_seh-1.dll', 'libwinpthread-1.dll',
                 'libssp-0.dll', 'libc++.dll', 'libunwind.dll', 'libatomic-1.dll', 'libgomp-1.dll'):
        runtime = pathlib.Path(output(compiler, '-print-file-name=' + name))
        if not runtime.is_absolute() or not runtime.is_file():
            runtime = compiler.parent / name
        if runtime.is_file():
            shutil.copy2(runtime, destination / name)


def prepare(profile, source, destination, target, renderers, patch=None):
    revision = profile['revision']
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        run('git', 'clone', '--filter=blob:none', '--no-checkout', profile['repository'], source)
        run('git', 'fetch', '--depth', '1', 'origin', revision, cwd=source)
        run('git', 'checkout', '--detach', revision, cwd=source)
    if output('git', 'rev-parse', 'HEAD', cwd=source) != revision:
        raise RuntimeError('source revision differs from selected pin; use a separate source directory')
    patch = patch or HERE / 'patches' / (profile['fork'] + '.patch')
    # A repeated prepare accepts only exactly this patch, never resets unrelated source edits.
    diff = subprocess.check_output(['git', 'diff', '--no-ext-diff', 'HEAD'], cwd=source)
    if diff:
        verify_applied_patch(source, patch)
    else:
        run('git', 'apply', '--check', patch, cwd=source)
        run('git', 'apply', patch, cwd=source)
    bridge = source / 'src' / 'yuzu_cmd' / 'emucap'
    bridge.mkdir(parents=True, exist_ok=True)
    for path in (HERE / 'native').iterdir():
        if path.is_file():
            shutil.copy2(path, bridge / path.name)
    for name in ('emucap_front_auth.h', 'emucap_native_failure.h',
                 'emucap_native_failure.cpp', 'emucap_atomic_file.h'):
        shutil.copy2(HERE.parent / '_common' / name, bridge / name)
    build_profile = {
        'schema': 'emucap-emulator-build/v1', 'family': 'eden-family',
        'fork': profile['fork'], 'repository': profile['repository'], 'revision': revision,
        'patch_sha256': patch_digest(patch), 'bridge_api': 1,
        'systems': profile['systems'], 'renderers': renderers,
        'cpu_features': cpu_features_for(target), 'target': target,
    }
    serialized = json.dumps(build_profile, sort_keys=True, separators=(',', ':'))
    adapter_build = output('git', 'rev-parse', 'HEAD', cwd=REPO)
    (bridge / 'EmucapBuildProfile.h').write_text(
        '#pragma once\ninline constexpr char EmucapBuildProfileJson[] = '
        + json.dumps(serialized) + ';\ninline constexpr char EmucapAdapterBuild[] = '
        + json.dumps(adapter_build) + ';\n', encoding='utf-8')
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'emucap-emulator-build.pending.json').write_text(
        json.dumps(build_profile, indent=2) + '\n', encoding='utf-8')
    return build_profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fork', choices=('eden', 'eden-nx2', 'eglantine'), default='eden')
    parser.add_argument('--profile', type=pathlib.Path, help='Explicit source descriptor for a compatible custom fork')
    parser.add_argument('--patch', type=pathlib.Path, help='Explicit integration patch required with --profile')
    parser.add_argument('--source', type=pathlib.Path)
    parser.add_argument('--output', type=pathlib.Path)
    parser.add_argument('--target')
    parser.add_argument('--cmake', default=os.environ.get('CMAKE', 'cmake'))
    parser.add_argument('--generator', default='Ninja')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--cmake-arg', action='append', default=[], help='Additional explicit CMake cache argument')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if bool(args.profile) != bool(args.patch):
        parser.error('--profile and --patch must be selected together')
    profile = json.loads((args.profile or HERE / 'profiles' / (args.fork + '.json')).read_text(encoding='utf-8'))
    if (not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', profile.get('fork', '')) or
            not re.fullmatch(r'(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})', profile.get('revision', '')) or
            not isinstance(profile.get('repository'), str) or not 0 < len(profile['repository']) <= 2048 or
            any(ord(c) < 32 for c in profile['repository'])):
        parser.error('source profile needs an explicit fork, repository and full revision')
    for field, allowed in [('systems', {'switch', 'switch2'}), ('renderers', {'vulkan', 'opengl'})]:
        values = profile.get(field)
        if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
            parser.error('source profile requires explicit ' + field)
        if len(values) != len(set(values)) or not set(values) <= allowed:
            parser.error('source profile has invalid ' + field)
    maintained_path = HERE / 'profiles' / (profile['fork'] + '.json')
    if maintained_path.is_file():
        maintained = json.loads(maintained_path.read_text(encoding='utf-8'))
        if any(profile[field] != maintained[field] for field in ('repository', 'revision')) or not set(profile['systems']) <= set(maintained['systems']):
            parser.error('custom source cannot replace a maintained fork identity; select a distinct fork name')
    for argument in args.cmake_arg:
        if re.match(r'-D(?:CMAKE_(?:C|CXX)_FLAGS[^=]*|YUZU_BUILD_PRESET|YUZU_USE_NATIVE_INSTRUCTIONS|ENABLE_OPENGL)(?::[^=]+)?=', argument):
            parser.error('--cmake-arg cannot override the generic CPU or advertised renderer build contract')
    source = (args.source or HERE / 'work' / (profile['fork'] + '-src')).resolve()
    destination = (args.output or HERE / 'build' / profile['fork'] / 'bin').resolve()
    machine = platform.machine().lower()
    if machine not in ('arm64', 'aarch64', 'x86_64', 'amd64'):
        parser.error('native recipe supports x86_64 and aarch64 hosts only')
    arch = 'aarch64' if machine in ('arm64', 'aarch64') else 'x86_64'
    target = args.target or arch + ('-pc-windows-gnu' if os.name == 'nt' else
                                   '-apple-darwin' if sys.platform == 'darwin' else '-unknown-linux-gnu')
    vulkan_only = sys.platform == 'darwin' or (os.name == 'nt' and arch == 'aarch64')
    renderers = [renderer for renderer in profile['renderers'] if not vulkan_only or renderer == 'vulkan']
    if not renderers:
        parser.error('selected source profile has no renderer supported by this platform recipe')
    build_profile = prepare(profile, source, destination, target, renderers, args.patch.resolve() if args.patch else None)
    if args.prepare_only:
        print('Prepared source and build profile only; no native build or guest qualification.')
        return
    build = destination.parent / 'cmake'
    options = ['-DENABLE_QT=OFF', '-DYUZU_CMD=ON', '-DYUZU_ROOM=OFF', '-DBUILD_TESTING=OFF',
               '-DENABLE_WEB_SERVICE=OFF', '-DUSE_DISCORD_PRESENCE=OFF', '-DENABLE_UPDATE_CHECKER=OFF',
               '-DENABLE_RESHADE=OFF', '-DENABLE_LSFG=OFF', '-DYUZU_USE_NATIVE_INSTRUCTIONS=OFF',
               '-DENABLE_LTO=OFF', '-DCMAKE_BUILD_TYPE=Release', '-DYUZU_BUILD_PRESET=generic',
               '-Dzstd_FORCE_BUNDLED=ON',
               '-DENABLE_OPENGL=' + ('ON' if 'opengl' in renderers else 'OFF')]
    if os.name == 'nt' or sys.platform == 'darwin':
        options.append('-DYUZU_USE_BUNDLED_FFMPEG=ON')
    if os.name == 'nt' and target.endswith('windows-gnu'):
        # httplib's optional async resolver references GetAddrInfoExCancel,
        # which is absent even from the tested MinGW-w64 14 headers.
        options.append('-DHTTPLIB_USE_NON_BLOCKING_GETADDRINFO=OFF')
        # Avoid windres's cmd.exe/popen limit with long dependency include paths.
        options.append('-DCMAKE_RC_FLAGS=--use-temp-file')
    if arch == 'x86_64':
        options.append('-DCMAKE_CXX_FLAGS=-march=x86-64 -mtune=generic')
    options.extend(windows_openssl_options(target, args.cmake_arg, source, build))
    run(args.cmake, '-S', source, '-B', build, '-G', args.generator, *options, *args.cmake_arg)
    run(args.cmake, '--build', build, '--target', 'yuzu-cmd', '--parallel', str(args.jobs))
    suffix = '.exe' if os.name == 'nt' else ''
    candidates = [directory / (name + suffix)
                  for directory in (build / 'bin', build / 'bin' / 'Release')
                  for name in ('eden-cli', 'yuzu-cmd', 'eden-sdl')]
    binary = next((path for path in candidates if path.is_file()), None)
    if binary is None:
        raise RuntimeError('native build produced no recognized SDL binary')
    shutil.copy2(binary, destination / ('eden-sdl' + suffix))
    for library in binary.parent.glob('*.dll'):
        shutil.copy2(library, destination / library.name)
    if os.name == 'nt' and target.endswith('windows-gnu'):
        copy_windows_runtime(build, destination)
    probe = subprocess.run([str(destination / ('eden-sdl' + suffix)), '--emucap-build-profile'],
                           capture_output=True, text=True, encoding='utf-8', timeout=15)
    if probe.returncode or len(probe.stdout) > 65536 or json.loads(probe.stdout) != build_profile:
        raise RuntimeError('Built executable did not return its matching compiled profile')
    metadata = destination / 'emucap-emulator-build.json'
    pending = metadata.with_suffix('.json.tmp')
    pending.write_text(json.dumps(build_profile, indent=2) + '\n', encoding='utf-8')
    pending.replace(metadata)
    print('Native build complete:', destination)
    print('No guest execution or live system qualification was performed.')


if __name__ == '__main__':
    main()

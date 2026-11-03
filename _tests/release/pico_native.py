"""Package the fork's locked DeSmuME build and its complete native runtime."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile

from package_native import files_manifest, linux_dependencies, run, sha, source_archive
from windows_native_payload import collect_imports, stage as stage_windows


def runtime_manifest(stage, executable, version, revision, upstream, patchset):
    return dict(adapter='desmume-nds', version=version, source_revision=revision,
                upstream_revision=upstream, patchset_sha256=patchset,
                executable=executable, files=files_manifest(stage))


def runtime_smoke(stage, manifest):
    env = dict(os.environ)
    env.pop('LD_LIBRARY_PATH', None)
    env.pop('DYLD_LIBRARY_PATH', None)
    if os.name == 'nt':
        windows = os.environ['SystemRoot']
        env['PATH'] = os.pathsep.join((str(Path(windows) / 'System32'), windows))
    else:
        env['PATH'] = os.defpath
    env['SDL_AUDIODRIVER'] = 'dummy'
    env['SDL_VIDEODRIVER'] = 'dummy'
    result = subprocess.run([str(stage / manifest['executable']), '--help'],
                            cwd=stage.parent, env=env, capture_output=True,
                            text=True, timeout=30)
    help_text = result.stdout + result.stderr
    # The native CLI deliberately exits 1 after printing help.
    if result.returncode not in (0, 1) or not all(
            option in help_text for option in ('--arm9gdb', '--cflash-image')):
        raise ValueError(f'Extracted native startup failed ({result.returncode}): {help_text[:6000]}')


def linux_notices(stage, notices, docs=Path('/usr/share/doc'), common=Path('/usr/share/common-licenses')):
    for library in sorted((stage / 'lib').iterdir()):
        ownership = run('dpkg-query', '-S', '*/' + library.name)
        owners = {line.split(': ', 1)[0].split(':', 1)[0] for line in ownership.splitlines()
                  if ': ' in line}
        if not owners:
            raise ValueError(f'No Debian package owns bundled library {library.name}')
        for owner in sorted(owners):
            target = notices / 'dependencies' / owner
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(docs / owner / 'copyright', target / 'copyright')
    shutil.copytree(common, notices / 'common-licenses')


def verify_archive(archive, name, smoke=False):
    with tempfile.TemporaryDirectory(prefix='pico-native-verify-') as temporary:
        root = Path(temporary)
        if archive.suffix == '.zip':
            with zipfile.ZipFile(archive) as packed:
                packed.extractall(root)
        else:
            with tarfile.open(archive) as packed:
                packed.extractall(root, filter='data')
        stage = root / name
        manifest = json.loads((stage / 'NATIVE-PACKAGE.json').read_text(encoding='utf-8'))
        actual = files_manifest(stage)
        actual.pop('NATIVE-PACKAGE.json')
        if actual != manifest['files']:
            raise ValueError('extracted native package manifest mismatch')
        if not (stage / manifest['executable']).is_file():
            raise ValueError('extracted native package lacks its executable')
        if smoke:
            runtime_smoke(stage, manifest)
            print(f'Extracted native startup passed: {archive.name}')


def checksum(path):
    path.with_name(path.name + '.sha256').write_bytes(f'{sha(path)}  {path.name}\n'.encode('ascii'))


def archive_runtime(stage, output, platform, smoke=False):
    output.mkdir(parents=True, exist_ok=True)
    archive = output / (stage.name + ('.zip' if platform == 'windows' else '.tar.gz'))
    if platform == 'windows':
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as packed:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    packed.write(path, stage.name + '/' + path.relative_to(stage).as_posix())
    else:
        with tarfile.open(archive, 'w:gz', compresslevel=3) as packed:
            packed.add(stage, arcname=stage.name)
    verify_archive(archive, stage.name, smoke=smoke)
    checksum(archive)
    return archive


def package(source, output, platform, dll_directories):
    source, output = source.resolve(), output.resolve()
    version = tomllib.loads((source / 'Cargo.toml').read_text(encoding='utf-8'))['package']['version']
    revision = run('git', '-C', source, 'rev-parse', 'HEAD')
    adapter = source / 'adapters/desmume-nds'
    lock = dict(line.split('=', 1) for line in (adapter / 'upstream.lock').read_text().splitlines()
                if line and not line.startswith('#'))
    upstream = adapter / 'work/src'
    if run('git', '-C', upstream, 'rev-parse', 'HEAD') != lock['DESMUME_COMMIT']:
        raise ValueError('native build source differs from upstream.lock')
    binary = upstream / 'desmume/src/frontend/posix/build-headless/cli' / (
        'desmume-cli.exe' if platform == 'windows' else 'desmume-cli')
    target = 'windows-x86_64' if platform == 'windows' else 'x86_64-unknown-linux-gnu'
    name = f'emucap-{version}-desmume-nds-{target}'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pico-native-stage-') as temporary:
        stage = Path(temporary) / name
        if platform == 'windows':
            stage_windows(binary, stage)
            collect_imports(stage, [binary.parent, *dll_directories],
                            [Path(os.environ['SystemRoot']) / 'System32'])
        else:
            stage.mkdir()
            shutil.copy2(binary, stage / binary.name)
            linux_dependencies(stage)
        notices = stage / 'licenses'
        notices.mkdir()
        shutil.copy2(source / 'NOTICE', notices / 'EMUCAP-NOTICE')
        for directory in (upstream, upstream / 'desmume'):
            for path in directory.iterdir():
                if path.is_file() and any(word in path.name.lower() for word in ('license', 'copying', 'copyright', 'notice')):
                    shutil.copy2(path, notices / path.name)
        # MSYS2 installs the DLL packages' license notices alongside its bin tree.
        for index, directory in enumerate(dll_directories):
            licenses = directory.parent / 'share/licenses'
            if licenses.is_dir():
                shutil.copytree(licenses, notices / f'dependencies-{index}')
        if platform == 'linux':
            linux_notices(stage, notices)
        manifest = runtime_manifest(stage, binary.name, version, revision,
                                    lock['DESMUME_COMMIT'], lock['DESMUME_PATCHSET_SHA256'])
        manifest['target'] = target
        (stage / 'NATIVE-PACKAGE.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        archive = archive_runtime(stage, output, platform, smoke=True)
        sources = source_archive(source, upstream, 'desmume-nds', output, name)
        checksum(sources)
        record = {key: value for key, value in manifest.items() if key != 'files'}
        record['artifacts'] = {path.name: sha(path) for path in (archive, sources)}
        (output / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, default=Path('artifacts'))
    parser.add_argument('--platform', choices=('windows', 'linux'), required=True)
    parser.add_argument('--dll-directory', type=Path, action='append', default=[])
    args = parser.parse_args()
    package(args.source, args.output, args.platform, args.dll_directory)

#!/usr/bin/env python3
"""Build a pinned Ryujinx-family frontend and its hash-bound native bridge."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / '_common'))
from build_support import maintained_source, verify_applied_patch as shared_verify_patch
JSON_URL = 'https://raw.githubusercontent.com/nlohmann/json/v3.12.0/single_include/nlohmann/json.hpp'
JSON_SHA256 = 'aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63'


def verified_json_header(include):
    header = include / 'nlohmann/json.hpp'
    if not header.is_file() or hashlib.sha256(header.read_bytes()).hexdigest() != JSON_SHA256:
        raise RuntimeError('native bridge requires the SHA-256-pinned nlohmann/json 3.12.0 single header')
    return header

def run(*args, cwd=None):
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)

def output(*args, cwd=None):
    return subprocess.check_output([str(a) for a in args], cwd=cwd, text=True).strip()

def verify_applied_patch(source, patch):
    return shared_verify_patch(source, patch, output=output, run=run)


def patch_digest(patch, header):
    files = [patch] + sorted((HERE / 'managed').glob('*.cs')) + sorted((HERE / 'native').glob('*'))
    files += sorted((HERE.parent / 'eden-family/native').glob('EmucapBridge.*'))
    files += [HERE.parent / '_common' / name for name in ('emucap_front_auth.h', 'emucap_native_failure.h', 'emucap_native_failure.cpp', 'emucap_atomic_file.h')]
    files.append(header)
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()

def validate_profile(profile, custom=False):
    if not isinstance(profile, dict) or set(profile) != {'fork','repository','reference','revision','systems','renderers'}:
        raise ValueError('profile requires fork, repository, reference, revision, systems, renderers')
    import re
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', profile['fork']) or not re.fullmatch('[0-9a-f]{40}', profile['revision']):
        raise ValueError('invalid fork or pinned revision')
    if not isinstance(profile['repository'], str) or not profile['repository'].startswith('https://') or any(ord(c) < 32 for c in profile['repository']):
        raise ValueError('repository must be an HTTPS source URL')
    if profile['systems'] != ['switch'] or not profile['renderers'] or any(r not in ('vulkan','opengl') for r in profile['renderers']) or len(set(profile['renderers'])) != len(profile['renderers']):
        raise ValueError('only Switch 1 and Vulkan/OpenGL are supported')
    maintained = HERE / 'profiles' / (profile['fork'] + '.json')
    if custom and maintained.exists() and profile != json.loads(maintained.read_text(encoding='utf-8-sig')):
        raise ValueError('custom profiles cannot impersonate a maintained fork')
    return profile

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fork', default='ryubing')
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--patch', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--dotnet', default='dotnet')
    parser.add_argument('--json-include', type=Path, help='nlohmann/json 3.12.0 include directory')
    args = parser.parse_args()
    if args.jobs < 1: parser.error('--jobs must be positive')
    if args.profile and not args.patch: parser.error('custom profiles require an explicit --patch')
    profile = validate_profile((json.loads(args.profile.read_text(encoding='utf-8-sig')) if args.profile else maintained_source(args.fork)), bool(args.profile))
    patch = (args.patch or HERE / 'patches' / (profile['fork'] + '.patch')).resolve()
    source = (args.source or HERE / 'work' / (profile['fork'] + '-src')).resolve()
    destination = (args.output or HERE / 'build' / profile['fork'] / 'bin').resolve()
    if platform.system() not in ('Windows', 'Linux'): raise RuntimeError('this recipe supports Windows/Linux hosts only')
    if platform.machine().lower() not in ('amd64','x86_64'): raise RuntimeError('this recipe currently qualifies x86_64 hosts only')
    rid, target, native_file = ('win-x64','x86_64-pc-windows-gnu','emucap-native.dll') if os.name == 'nt' else ('linux-x64','x86_64-unknown-linux-gnu','libemucap-native.so')
    if not source.exists():
        run('git','clone','--filter=blob:none','--no-checkout',profile['repository'],source)
        run('git','checkout','--detach',profile['revision'],cwd=source)
    if output('git','rev-parse','HEAD',cwd=source) != profile['revision']: raise RuntimeError('source HEAD does not match pinned profile')
    untracked = output('git','ls-files','--others','--exclude-standard',cwd=source).splitlines()
    allowed = {'src/Ryujinx/Emucap/' + p.name for p in (HERE / 'managed').glob('*.cs')} | {'src/Ryujinx/Emucap/EmucapBuild.cs'}
    if set(untracked) - allowed: raise RuntimeError('source has unrelated untracked files')
    if not output('git','diff','--name-only','HEAD',cwd=source): run('git','apply','--check',patch,cwd=source); run('git','apply',patch,cwd=source)
    verify_applied_patch(source,patch)
    include = args.json_include
    if include is None:
        include = HERE / 'work' / 'json-3.12.0' / 'include'
        if not (include / 'nlohmann/json.hpp').exists():
            with urllib.request.urlopen(JSON_URL, timeout=30) as response:
                data = response.read(2 * 1024 * 1024)
            if hashlib.sha256(data).hexdigest() != JSON_SHA256:
                raise RuntimeError('pinned JSON download digest mismatch')
            (include / 'nlohmann').mkdir(parents=True, exist_ok=True)
            (include / 'nlohmann/json.hpp').write_bytes(data)
    include = include.resolve()
    header = verified_json_header(include)
    destination.mkdir(parents=True,exist_ok=True)
    (destination / 'emucap-emulator-build.json').unlink(missing_ok=True)
    native = destination / native_file
    flags = ['-std=c++20','-O1','-Wall','-Wextra','-Werror','-pthread','-shared']
    flags += ['-static'] if os.name == 'nt' else ['-fPIC']
    flags += ['-I' + str(HERE.parent / '_common'), '-I' + str(include)]
    sources = [HERE / 'native/EmucapNative.cpp', HERE.parent / 'eden-family/native/EmucapBridge.cpp', HERE.parent / '_common/emucap_native_failure.cpp']
    run(args.cxx,*flags,*sources,*(['-lws2_32'] if os.name == 'nt' else []),'-o',native)
    profile_built = dict(schema='emucap-emulator-build/v1',family='ryujinx-family',fork=profile['fork'],repository=profile['repository'],revision=profile['revision'],patch_sha256=patch_digest(patch, header),bridge_api=1,systems=profile['systems'],renderers=profile['renderers'],cpu_features=[],target=target)
    serialized = json.dumps(profile_built,sort_keys=True,separators=(',',':'))
    pending = destination / 'emucap-emulator-build.pending.json'
    pending.write_text(json.dumps(profile_built,indent=2)+'\n',encoding='utf-8')
    managed = source / 'src/Ryujinx/Emucap'
    managed.mkdir(exist_ok=True)
    for path in (HERE / 'managed').glob('*.cs'): shutil.copy2(path,managed/path.name)
    constants = {'Profile':serialized,'AdapterBuild':output('git','rev-parse','HEAD',cwd=REPO),'NativeFile':native_file,'NativeSha256':hashlib.sha256(native.read_bytes()).hexdigest()}
    (managed / 'EmucapBuild.cs').write_text('// Generated by emucap; do not edit.\nnamespace Ryujinx.Headless;\ninternal static class EmucapBuild {\n' + ''.join('    internal const string '+k+' = '+json.dumps(v)+';\n' for k,v in constants.items()) + '}\n',encoding='utf-8')
    run(args.dotnet,'publish',source / 'src/Ryujinx/Ryujinx.csproj','-c','Release','-r',rid,'--self-contained','false','-p:PublishSingleFile=false','-p:PublishTrimmed=false','-m:'+str(args.jobs),'-o',destination)
    probe = subprocess.run([str(destination / ('Ryujinx.exe' if os.name == 'nt' else 'Ryujinx')),'--emucap-build-profile'],capture_output=True,text=True,encoding='utf-8',timeout=20)
    if probe.returncode or len(probe.stdout)>65536 or json.loads(probe.stdout) != profile_built: raise RuntimeError('built executable did not return its matching compiled profile: '+probe.stderr)
    pending.replace(destination / 'emucap-emulator-build.json')
    print('Built hash-bound frontend:',destination)
    print('Guest execution and live qualification have not been performed by this recipe.')

if __name__ == '__main__': main()

#!/usr/bin/env python3
"""Admit explicit native/homebrew artifacts, then run the managed guest witness harness."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def require_system(fork, system):
    if ((fork == 'azahar') != (system == '3ds')
            or (fork in ('eden', 'ryubing') and system == 'switch2')):
        raise ValueError('This fork does not implement the requested target system')


def linux_frontend(payload, fork):
    return payload / ('Ryujinx' if fork == 'ryubing' else 'eden-sdl')


def fixture_content(directory, system):
    directory = directory.resolve()
    fixture = json.loads((directory / 'fixture.json').read_text(encoding='utf-8'))
    license_field = 'source_license' if system == 'switch2' else 'license'
    if fixture['system'] != system or fixture.get(license_field) != 'CC0-1.0':
        raise ValueError('A matching lawful source-built witness fixture is required')
    content = (directory / fixture['content']).resolve(strict=True)
    if not content.is_relative_to(directory) or not content.is_file():
        raise ValueError('Fixture content escapes its artifact')
    source = ROOT / '_tests/live/emulator-family' / ('ctr.c' if system == '3ds' else 'switch.c')
    if hashlib.sha256(source.read_bytes()).hexdigest() != fixture['source_sha256']:
        raise ValueError('Fixture source differs from this checkout witness')
    if system == 'switch2':
        members = fixture.get('members')
        if (fixture.get('content') != 'exefs/main' or not isinstance(members, dict)
                or set(members) != {'main', 'main.npdm'}
                or {path.name for path in content.parent.iterdir()} != set(members)):
            raise ValueError('Switch 2 fixture requires the exact two-member ExeFS graph')
        for name, digest in members.items():
            member = content.parent / name
            if (member.is_symlink() or not member.is_file()
                    or hashlib.sha256(member.read_bytes()).hexdigest() != digest):
                raise ValueError('Switch 2 member digest differs from its build record')
        descriptor = ROOT / '_tests/live/emulator-family/ounce-witness.npdm.json'
        if hashlib.sha256(descriptor.read_bytes()).hexdigest() != fixture.get('descriptor_sha256'):
            raise ValueError('Switch 2 descriptor differs from this checkout witness')
        config = directory / 'emulator.ini'
        if (config.is_symlink() or not config.is_file()
                or hashlib.sha256(config.read_bytes()).hexdigest() != fixture.get('emulator_config_sha256')):
            raise ValueError('Switch 2 config digest differs from its build record')
        if (not re.fullmatch('[0-9a-f]{40}', str(fixture.get('libnx_ounce_revision', '')))
                or not re.fullmatch('[0-9a-f]{64}', str(fixture.get('libnx_ounce_library_sha256', '')))):
            raise ValueError('Switch 2 fixture requires runtime source and archive provenance')
    elif hashlib.sha256(content.read_bytes()).hexdigest() != fixture['fixture_sha256']:
        raise ValueError('Fixture artifact digest differs from its build record')
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fork', required=True, choices=('azahar', 'eden', 'eden-nx2', 'eglantine', 'ryubing'))
    parser.add_argument('--system', required=True, choices=('3ds', 'switch', 'switch2'))
    parser.add_argument('--native', required=True, type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--approve-indirect-media', action='store_true',
                        help='Explicitly confirm review of the source-built composite fixture and config')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {'proof_level': 'live-guest-witness', 'fork': args.fork,
              'system': args.system, 'status': 'blocked', 'live_qualified': False}
    try:
        require_system(args.fork, args.system)
        if args.system == 'switch2' and not args.approve_indirect_media:
            raise ValueError('Switch 2 requires explicit reviewed composite-fixture approval')
        native = args.native.resolve()
        build = json.loads((native / 'native-build-results.json').read_text(encoding='utf-8'))
        if build['status'] != 'passed' or build['fork'] != args.fork:
            raise ValueError('A successful matching native-source-build artifact is required')
        payload = native / 'payload'
        profile = payload / 'emucap-emulator-build.json'
        content = fixture_content(args.fixture, args.system)
        command = [sys.executable, str(ROOT / '_tests/live/emulator-family/qualify.py'),
                   '--mcp', str(ROOT / 'target/release/emucap-mcp'),
                   '--fork', args.fork, '--system', args.system, '--content', str(content),
                   '--profile', str(profile), '--output', str(output / 'guest')]
        if args.system == 'switch2':
            command += ['--config', str(args.fixture.resolve() / 'emulator.ini'), '--approve-indirect-media']
        environment = dict(os.environ)
        if args.fork == 'ryubing':
            config = output / 'ryubing-config.json'
            config.write_text(json.dumps({'memory_manager_mode': 'SoftwarePageTable'}) + '\n', encoding='utf-8')
            command += ['--config', str(config)]
            environment['DOTNET_EnableAlternateStackCheck'] = '1'
        if args.fork == 'azahar':
            core = payload / 'azahar_libretro.so'
            if not core.is_file():
                raise ValueError('The Linux software libretro core is missing')
            command += ['--binary', str(ROOT / 'target/release/emucap-azahar'), '--core', str(core),
                        '--python', sys.executable, '--renderer', 'software']
        else:
            binary = linux_frontend(payload, args.fork)
            if not binary.is_file():
                raise ValueError('The selected Linux emulator frontend is missing')
            command += ['--binary', str(binary), '--renderer', 'vulkan', '--display']
        if not Path(command[1]).is_file():
            raise ValueError('The live guest witness harness is unavailable')
        result['command'] = command
        result['status'] = 'failed'
        with (output / 'live.log').open('w', encoding='utf-8') as log:
            process = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=300)
        result['exit_code'] = process.returncode
        process.check_returncode()
        witness = json.loads((output / 'guest/result.json').read_text(encoding='utf-8'))
        if witness.get('status') != 'passed':
            raise ValueError('Guest harness did not report a passed witness result')
        result['status'] = 'passed'
        result['live_qualified'] = True
        result['unqualified'] = witness.get('unqualified', [])
        result['qualification_scope'] = 'guest counter, persistent digital/analog/touch, capture, progress, managed lifecycle for exact fixture/config'
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        (output / 'live-job-results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

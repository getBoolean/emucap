#!/usr/bin/env python3
"""Admit explicit native/homebrew artifacts, then run the managed guest witness harness."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def fixture_content(directory, system):
    directory = directory.resolve()
    fixture = json.loads((directory / 'fixture.json').read_text(encoding='utf-8'))
    if fixture['system'] != system or fixture.get('license') != 'CC0-1.0':
        raise ValueError('A matching lawful source-built witness fixture is required')
    content = (directory / fixture['content']).resolve(strict=True)
    if not content.is_relative_to(directory) or not content.is_file():
        raise ValueError('Fixture content escapes its artifact')
    if hashlib.sha256(content.read_bytes()).hexdigest() != fixture['fixture_sha256']:
        raise ValueError('Fixture artifact digest differs from its build record')
    if system in ('3ds', 'switch'):
        source = ROOT / '_tests/live/emulator-family' / ('ctr.c' if system == '3ds' else 'switch.c')
        if hashlib.sha256(source.read_bytes()).hexdigest() != fixture['source_sha256']:
            raise ValueError('Fixture source differs from this checkout witness')
    elif not fixture.get('source') or len(fixture.get('source_sha256', '')) != 64:
        raise ValueError('Switch 2 requires separate lawful source provenance and actual target metadata')
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fork', required=True, choices=('azahar', 'eden', 'eden-nx2', 'eglantine'))
    parser.add_argument('--system', required=True, choices=('3ds', 'switch', 'switch2'))
    parser.add_argument('--native', required=True, type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {'proof_level': 'live-guest-witness', 'fork': args.fork,
              'system': args.system, 'status': 'blocked', 'live_qualified': False}
    try:
        if (args.fork == 'azahar') != (args.system == '3ds') or (args.fork == 'eden' and args.system == 'switch2'):
            raise ValueError('This fork does not implement the requested target system')
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
        if args.fork == 'azahar':
            core = payload / 'azahar_libretro.so'
            if not core.is_file():
                raise ValueError('The Linux software libretro core is missing')
            command += ['--binary', str(ROOT / 'target/release/emucap-azahar'), '--core', str(core),
                        '--python', sys.executable, '--renderer', 'software']
        else:
            command += ['--binary', str(payload / 'eden-sdl'), '--renderer', 'vulkan', '--display']
        if not Path(command[1]).is_file():
            raise ValueError('The live guest witness harness is unavailable')
        result['command'] = command
        result['status'] = 'failed'
        with (output / 'live.log').open('w', encoding='utf-8') as log:
            process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=300)
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

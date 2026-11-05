"""Shared source descriptors and exact-patch admission for build recipes."""
import json
from pathlib import Path, PureWindowsPath
import subprocess
import tempfile

ADAPTERS = Path(__file__).resolve().parent.parent
SOURCE_DESCRIPTORS = {
    'azahar': ADAPTERS / 'azahar/upstream.lock',
    **{fork: ADAPTERS / 'eden-family/profiles' / (fork + '.json')
       for fork in ('eden', 'eden-nx2', 'eglantine')},
    'ryubing': ADAPTERS / 'ryujinx-family/profiles/ryubing.json',
    **{fork: ADAPTERS / 'libretro/profiles' / (fork + '.json') for fork in ('mgba', 'melonds')},
}


def maintained_source(fork):
    return json.loads(SOURCE_DESCRIPTORS[fork].read_text(encoding='utf-8-sig'))


def verify_applied_patch(source, patch, *, output, run, path_type=Path,
                         invalid_patch='patch must modify existing source files exactly once',
                         outside='source has edits outside the exact selected patch',
                         unsafe='unsafe patch path',
                         changed='source differs from the exact selected patch: '):
    paths = [line[6:] for line in patch.read_text(encoding='utf-8').splitlines()
             if line.startswith('+++ b/')]
    if not paths or len(paths) != len(set(paths)):
        raise RuntimeError(invalid_patch)
    if set(output('git', 'diff', '--name-only', 'HEAD', cwd=source).splitlines()) != set(paths):
        raise RuntimeError(outside)
    with tempfile.TemporaryDirectory(prefix='emucap-patch-verify-') as temporary:
        baseline = Path(temporary)
        for name in paths:
            relative = path_type(name)
            windows_path = PureWindowsPath(name)
            if relative.anchor or windows_path.anchor or '..' in relative.parts or '..' in windows_path.parts:
                raise RuntimeError(unsafe)
            target = baseline / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=source))
        run('git', 'apply', patch, cwd=baseline)
        for name in paths:
            if ((source / name).read_bytes().replace(b'\r\n', b'\n') !=
                    (baseline / name).read_bytes().replace(b'\r\n', b'\n')):
                raise RuntimeError(changed + name)

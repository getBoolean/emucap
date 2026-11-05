#!/usr/bin/env python3
"""Recipe admission tests; full managed/frontend builds belong to live qualification."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('ryujinx_build', Path(__file__).resolve().parents[1] / 'build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

class BuildTests(unittest.TestCase):
    def test_version_macros_cannot_impersonate_the_pinned_header(self):
        with tempfile.TemporaryDirectory() as directory:
            include = Path(directory)
            (include / 'nlohmann').mkdir()
            (include / 'nlohmann/json.hpp').write_text(
                '#define NLOHMANN_JSON_VERSION_MAJOR 3\n#define NLOHMANN_JSON_VERSION_MINOR 12\n'
                '#define NLOHMANN_JSON_VERSION_PATCH 0\n// altered implementation\n', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'SHA-256-pinned'):
                build.verified_json_header(include)

    def test_exact_applied_patch_rejects_extra_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'a.txt').write_text('changed\n', encoding='utf-8', newline='\n')
            selected = root / 'selected.patch'
            selected.write_text('diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-before\n+changed\n', encoding='utf-8', newline='\n')
            with patch.object(build, 'output', return_value='a.txt'), patch.object(build.subprocess, 'check_output', return_value=b'before\n'):
                build.verify_applied_patch(source, selected)
                (source / 'a.txt').write_text('changed\nhidden edit\n', encoding='utf-8', newline='\n')
                with self.assertRaisesRegex(RuntimeError, 'differs from'):
                    build.verify_applied_patch(source, selected)

    def test_other_tracked_file_rejected_before_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = Path(directory) / 'selected.patch'
            selected.write_text('+++ b/a.txt\n', encoding='utf-8', newline='\n')
            with patch.object(build, 'output', return_value='a.txt\nother.txt'), patch.object(build, 'run') as apply:
                with self.assertRaisesRegex(RuntimeError, 'outside'):
                    build.verify_applied_patch(Path(directory), selected)
                apply.assert_not_called()

    def test_custom_fork_does_not_impersonate_maintained_source(self):
        profile = json.loads((build.HERE / 'profiles/ryubing.json').read_text(encoding='utf-8-sig'))
        build.validate_profile(profile, custom=True)
        profile['repository'] = 'https://example.com/other.git'
        with self.assertRaisesRegex(ValueError, 'impersonate'):
            build.validate_profile(profile, custom=True)
        profile['fork'] = 'explicit-custom'
        build.validate_profile(profile, custom=True)
        profile['systems'] = ['switch2']
        with self.assertRaisesRegex(ValueError, 'Switch 1'):
            build.validate_profile(profile, custom=True)

if __name__ == '__main__': unittest.main()

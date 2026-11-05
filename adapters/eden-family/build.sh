#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
source "$here/../_common/build-env.sh"
emucap_scrub_build_env
exec "${PYTHON:-python3}" "$here/build.py" "$@"

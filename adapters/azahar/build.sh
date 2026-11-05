#!/bin/sh
set -eu
exec "${PYTHON:-python3}" "$(dirname "$0")/build.py" "$@"

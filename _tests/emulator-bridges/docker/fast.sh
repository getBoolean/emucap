#!/usr/bin/env bash
set -euo pipefail
mkdir -p /state/tmp /state/pip
g++ --version
git --version
python --version
python -m pip install Pillow==11.3.0
python _tests/emulator-bridges/fast.py --evidence /evidence/results --cc gcc --cxx g++

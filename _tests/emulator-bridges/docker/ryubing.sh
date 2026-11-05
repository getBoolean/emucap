#!/usr/bin/env bash
set -euo pipefail
export DOTNET_CLI_HOME=/work/dotnet-home NUGET_PACKAGES=/work/nuget
export CARGO_HOME=/work/cargo RUSTUP_HOME=/work/rustup
export CARGO_BUILD_JOBS=4
export PATH="$CARGO_HOME/bin:$PATH"
export TMPDIR=/work/tmp
mkdir -p "$TMPDIR"
status=failed
trap 'code=$?; printf "{\"status\":\"%s\",\"exit_code\":%d}\n" "$status" "$code" > /evidence/docker-result.json' EXIT
dotnet --version
git config --global --add safe.directory /workspace
if [ ! -d /work/ryubing-src/.git ]; then
    git -c safe.directory=/upstream clone --no-local /upstream /work/ryubing-src
fi
mkdir -p /work/json/include/nlohmann
if [ ! -f /work/json/include/nlohmann/json.hpp ]; then
    curl --fail --location --silent --show-error \
      https://raw.githubusercontent.com/nlohmann/json/v3.12.0/single_include/nlohmann/json.hpp \
      --output /work/json/include/nlohmann/json.hpp
fi
python /workspace/adapters/ryujinx-family/build.py --fork ryubing \
    --source /work/ryubing-src --output /evidence/payload --jobs 8 \
    --json-include /work/json/include
if ! command -v rustc >/dev/null; then
    curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
      https://sh.rustup.rs --output /work/emucap-rustup.sh
    sh /work/emucap-rustup.sh -y --profile minimal --default-toolchain 1.94.1
fi
rustc --version
CARGO_TARGET_DIR=/work/cargo-target cargo build --locked --release \
    --manifest-path /workspace/Cargo.toml --bin emucap-mcp
cp /work/cargo-target/release/emucap-mcp /evidence/emucap-mcp
chmod a+rx /evidence /evidence/payload /evidence/payload/Ryujinx /evidence/emucap-mcp
mkdir -p /evidence/live
chmod a+rwx /evidence/live
printf '{"memory_manager_mode":"SoftwarePageTable"}\n' > /evidence/linux-config.json
runuser -u emucap -- env TMPDIR=/tmp LIBGL_ALWAYS_SOFTWARE=1 SDL_AUDIODRIVER=dummy DOTNET_EnableAlternateStackCheck=1 \
    xvfb-run -a -s '-screen 0 1280x720x24' \
    python /workspace/_tests/live/emulator-family/qualify.py \
      --mcp /evidence/emucap-mcp --fork ryubing --system switch \
      --binary /evidence/payload/Ryujinx --profile /evidence/payload/emucap-emulator-build.json \
      --content /fixture/witness.nro --renderer vulkan --output /evidence/live/guest \
      --config /evidence/linux-config.json
status=passed

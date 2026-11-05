# melonDS DS and mGBA software cores

Opt-in DS/GBA automation through the shared supervised libretro worker. Desktop
melonDS 1.1 and mGBA 0.10.5 are separate portable applications; this adapter does
not control their Qt windows. Existing DeSmuME/Mesen2 defaults remain available.

The maintained automation builds use mGBA 0.10.5
(`26b7884bc25a5933960f3cdcd98bac1ae14d42e2`) and Jesse Talavera-Greenberg's
[melonDS DS](https://github.com/JesseTG/melonds-ds) v1.4.0
(`f394adbacb5722ee97c1b37c8064da9a25818310`). The latter is a libretro frontend
for melonDS, not the stock melonDS 1.1 desktop executable.

## Build and select

Maintained pins and core target names live in `profiles/*.json`. The build
helper reads these descriptors, and Rust embeds the same pin data for admission.

Use a recursive checkout of the exact pin and an out-of-source CMake build.
For mGBA configure `BUILD_LIBRETRO=ON`, `SKIP_LIBRARY=ON`, `BUILD_QT=OFF`,
`BUILD_SDL=OFF`, `CMAKE_BUILD_TYPE=Release`; optional external dependencies may
be disabled. CMake 4 requires `CMAKE_POLICY_VERSION_MINIMUM=3.5` for this tag.
For melonDS DS configure `ENABLE_OPENGL=OFF`, `ENABLE_JIT=OFF`,
`BUILD_TESTING=OFF`, `CMAKE_BUILD_TYPE=Release`. Its FetchContent dependencies
require network access at configure time. No Docker is required.

After configuration:

```powershell
py -3.12 adapters/libretro/build.py --fork mgba --source B:/dev/build/emucap-mgba-core --build B:/dev/build/emucap-mgba-core/build-emucap
py -3.12 adapters/libretro/build.py --fork melonds --source B:/dev/build/emucap-melonds-core --build B:/dev/build/emucap-melonds-core/build-emucap
cargo build --release --bin emucap-azahar --bin emucap-mcp
```

The build helper rejects a different/dirty tracked source revision and adds a
generated identity translation unit without editing upstream source. Keep the
emitted `emucap-emulator-build.json` next to the shared library. Supply any native
runtime dependencies alongside it. The Windows builds qualified here link their
compiler runtimes statically. Build recipes and pinned upstream source, not
downloaded desktop binaries, produce this adapter's libraries.

Pass the same explicit object to MCP `launch_plan` and then `launch`:

```json
{
  "system": "nds",
  "content_path": "C:/homebrew/input-lab.nds",
  "emulator": {
    "fork": "melonds",
    "core": "B:/tools/emucap/libretro/melonds/melondsds_libretro.dll"
  }
}
```

For GBA use `system: "gba"`, `fork: "mgba"` and `mgba_libretro.dll`.
`python`, `profile` and supervisor `binary` may be selected explicitly.
`EMUCAP_MELONDS_CORE` / `EMUCAP_MGBA_CORE` select the core when the corresponding
explicit emulator object omits `core`. The existing `emucap-azahar` executable
is reused as the shared supervisor; `EMUCAP_AZAHAR_HOST` overrides its path.
This retains its process ownership, authentication, bounded transport, native
hang retirement, reconnect cleanup and managed stop behavior.

## Capabilities and boundaries

| Operation | mGBA / GBA | melonDS DS / DS |
| --- | --- | --- |
| Launch / owned stop | Yes | Yes |
| Software PNG capture | 240x160 | 256x384, top then bottom, gap 0 |
| Persistent buttons, port 0 | A/B, L/R, Select/Start, D-pad | Also X/Y |
| Persistent touch | Absent | One contact, bottom-screen 256x192 |
| Wait for observed software callbacks | Yes | Yes |
| Exact step, pause, timed tap/touch | Absent | Absent |
| Audio playback / GUI | Absent | Absent |

Input replaces the complete button state; omitted touch remains held until
explicit release. Axes, other ports and unsupported controls reject requests.
The accepted software-callback counter is an observation domain, not proof of
one guest frame per host call. The owner runs continuously with wall-clock
pacing; no determinism claim follows from the libretro `retro_run` API.

DS uses built-in replacement BIOS/firmware and direct boot for original
homebrew. GBA uses its built-in replacement BIOS. No original BIOS, firmware,
keys or commercial games are obtained. DSi, GB/GBC, arbitrary cartridge
peripherals, microphone, link/network play, external DLDI image selection and
desktop-GUI automation are not exposed by these profiles. melonDS DS may create
its own managed storage files; those do not implement DeSmuME's external
`nds_storage_image` contract. Display, second-content and external-image requests
are rejected before launch.

## Validation and headless CI

```powershell
py -3.12 -m unittest discover -s adapters/libretro -p 'test_*.py'
py -3.12 -m unittest discover -s adapters/azahar -p 'test_*.py'
py -3.12 _tests/input-lab/qualify.py --mcp target/release/emucap-mcp.exe --launch-json selection.json --output evidence-new
```

The original Input Lab fixture must be built first; see its README. The live
runner verifies guest build ID, CRC, fresh sample, all advertised buttons
(hold/sustained/release), DS touch edges/centre, combined state and final release.
It stops the owned generation and preserves failed-run state. Pillow is needed
only by the image oracle. Unit tests join the existing cross-platform bridge
fast CI lane; that lane does not build or run the actual emulator cores.

Windows live results and precise limitations are recorded in
[the Input Lab qualification record](../../docs/input-lab-qualification.md).
Linux/macOS core builds and live runs have not been qualified here. Upstream
source licenses and bundled dependency notices must accompany redistributed
builds; see [CREDITS](../../CREDITS.md) and [NOTICE](../../NOTICE).

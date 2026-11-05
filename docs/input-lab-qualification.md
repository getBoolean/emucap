# Input Lab local qualification

Date: 2026-11-04. Checkout: `B:/dev/GitHub/emucap`, branch
`feat/azahar-libretro-bridge`. Changes are local and uncommitted; no push/PR.
Gyro/motion was removed by user direction. This is an initial native
implementation, not completion of the all-platform product contract.

## Implementation and checks

- `_tests/input-lab/`: shared original C raster UI/encoder; native Switch, Ounce,
  3DS, DS/GBA and GC/Wii sampling/rendering; explicit cross-builder and artwork
  converter; independent Python image decoder/full-state oracle; live runner.
- `docs/design/input-lab-preview.html` and the design plan: gyro removed;
  controller specimen returned to its default view and labeled simulated.
- `docs/design/assets/procon/`, CREDITS.md, NOTICE: retained input-viewer artwork,
  provenance and full terms; native raster usage and conversion tools credited.
- `.github/workflows/input-lab.yml`: host C/image contract tests only. Remote CI
  has not run. This job does not claim native boot or live input qualification.
- `adapters/eden-family/native/EmucapBridge.cpp`: the forced Pro Controller profile
  now advertises/rejects the actual guest-readable button set. SL/SR are gated
  to Joy-Con styles in upstream HID; Home/Capture have no ordinary pad readback.
  The separate Ryubing branch retains its independently observed 18-button set.
- `adapters/eden-family/tests/run.py`: exact advertised-set and rejected-control
  regressions. The new assertion failed before the capability fix. The Unicode
  endpoint fixture now uses the C++20 UTF-8 path constructor; its old HEAD source
  reproduced GCC 16's `u8path` deprecation under warnings-as-errors.

Eight Input Lab tests passed on Windows/Clang and Linux/GCC through the existing
Compose file. They compile the real C renderer, decode independent 160x144 and
scaled captures, verify full-width/native values and transitions, reject corrupt
records, wrong controls/axes/ports/touch/targets/build IDs and stale samples,
accept sequence rollover, and reproduce/fix failed-stop process leaks and lost
terminal evidence. Tests are not live emulator evidence.

All nine existing Linux bridge fast lanes passed, including Eden and Ryubing
native endpoint/ABI checks. After the Unicode fixture change, the focused Eden
endpoint suite passed again on Windows GCC 16 and Linux GCC. Four Eden build
recipe tests passed. Python compilation and `git diff --check` passed.

The Compose service was reused with explicit container name
`emucap-bridge-fast-linux`, project `emucap-input-lab`, read-only checkout bind,
and separate host evidence/state binds. Mount inspection showed bind mounts
only. Its container and project network were removed; bind data was retained.

## Native build proof

All seven targets cross-built with `-Wall -Wextra -Werror`. Current artifacts,
commands, compiler versions, source hashes, build IDs and full artifact hashes:

`C:/Users/Boolean/AppData/Local/Temp/emucap-input-lab/<system>-reviewed/fixture.json`

| System | Artifact | Embedded build ID |
| --- | --- | --- |
| switch | input-lab.nro | 159ca1e35f216bccb14d404e6e25e24a |
| 3ds | input-lab.3dsx | 5cf1cf10b9eaebdae0def50095c96f1a |
| nds | input-lab.nds | c9b9fc82ffb46196cd36d08533831901 |
| gba | input-lab.gba | ed54ec7c7a8932e9a272d41e0e8425f3 |
| gamecube | input-lab.dol | e49095705944997887e3eaa098f4f08e |
| wii | input-lab.dol | 39a832f6f5b8cd5edbec3929883e4dda |
| switch2 | exefs/main + main.npdm | f06e57db0e4cec2b9fd983e1907630be |

Switch 2 uses pinned libnx-ounce
`a04b88b3d3ed059963200d0a3d460754b2fe294e`, archive SHA256
`c7a13c770a79c0381ed2a2fc351aa07ad8cc2738e515c17029d61962098f9887`,
and the existing reviewed Ounce-only unsigned NPDM builder. Its 12 GiB emulator
layout and 64 MiB guest heap remain explicit. No commercial content, firmware or
keys were acquired.

## Live evidence

Evidence root: `C:/Users/Boolean/AppData/Local/Temp/emucap-input-lab/`.
`qualified-identities.json` records explicit selections and SHA256 identities
for the MCP, frontend, guest, core/profile and config files used. Each live folder
contains captures, decoded observations, runtime status, native logs, stop result
and terminal `result.json`. Failed attempts are preserved alongside successful
ones; earlier `-final`/`-reviewed` Eglantine attempts are not passes.

The runner checks every advertised button individually (hold, sustained hold,
release); six signed quarter/half/full magnitudes per axis; absence of cross-axis
activity; all four touch corners and centre; combined controls; and full release.
Every accepted sample has a fresh guest sequence and exact embedded build ID.
Counts below are accepted observation checkpoints, not separate independent
features or proof of deterministic stepping.

| Emulator / guest | Result | Checkpoints | Evidence directory |
| --- | --- | --- | --- |
| Azahar / 3DS | Passed again after shared-worker changes, software | 100 | live-azahar-shared-final-002 |
| Ryubing / Switch | Passed, Vulkan | 112 | live-ryubing-reviewed |
| Eden / Switch | Passed, Vulkan | 106 | live-eden-reviewed |
| Eden-NX2 / Ounce Switch 2 | Passed, Vulkan | 106 | live-eden-nx2-reviewed |
| Djihads80 Eglantine / Ounce Switch 2 | Passed, pixel-exact Vulkan config | 106 | live-eglantine-pixel-exact |
| melonDS DS v1.4.0 / DS | Passed, software, buttons and touch | 49 | live-melonds-final-002 |
| mGBA 0.10.5 / GBA | Passed, software, buttons | 37 | live-mgba-final-002 |
| Dolphin / GameCube | Passed, raw-XFB D3D capture, digital input | 41 | live-dolphin-gamecube-raw-002 |
| Dolphin / Wii | Passed, raw-XFB D3D capture, Remote core buttons | 38 | live-dolphin-wii-raw-002 |

All nine successful configurations reported completed managed stop. The total
is 695 accepted guest-observation checkpoints; the new Azahar rerun replaces
its earlier 100 rather than being counted twice. These cover only
the exact original fixtures, current profiles and recorded configurations.

Eden-family frontends were rebuilt from the maintained pins with these bridge
digests after the capability correction:

| Fork | Patch digest |
| --- | --- |
| Eden | f7ff01a42d9df1281d06e09dcc9403b8813877f32d8cc5b52d97dd7252dad93b |
| Eden-NX2 | 14e620cf6be92bff342ae6d562651ab7b946ca5970702041a802787890780ec0 |
| Eglantine | 81089d518acef55d6fabdd9e9ac638ab849a4adcb27cff11be39827e6ca7bb22 |

Eglantine defaults to both FXAA and ScaleForce. The tiny record failed strict
monochrome/CRC validation with those filters. Its pixel-exact qualification uses
`anti_aliasing=0`, `scaling_filter=0`, both explicit nondefault settings, while
retaining the selected Intel Vulkan device and Ounce memory layout. The decoder
thresholds were not weakened to turn those failed captures into passes.

## Remaining acceptance gates

Earlier saved default DS/GBA/GC/Wii launch-plan snapshots recorded missing
binaries. They remain historical evidence. Explicit melonDS DS and mGBA core
selections now pass original-guest input/capture tests, including rejected
unsupported requests preserving the held state. Stock desktop applications have
installation/version checks only. Existing DeSmuME/Mesen2 defaults were retained.
DS uses replacement system files/direct boot, GBA its built-in replacement BIOS.
DSi, GB/GBC, microphone and external storage-image selection remain unqualified
or absent from these profiles. See `adapters/libretro/README.md`.

Dolphin is now built and its GC/Wii digital input passes. A CPU-written XFB guest
never emits the GX frame-end event previously required to flush screenshot
readback. The new `FrameDumper-vi-screenshot-flush.patch` flushes a pending
screenshot on the video owner at presentation. Managed launch selects
`Graphics.Settings.FrameDumpsResolutionType=2` for raw XFB pixels. Earlier
screenshot timeouts and aspect-stretched captures remain failed evidence.
The pinned Dolphin commit is `409881c34357d0f105fd473167d15ab0bd9c1628`, patchset
`92174033977016b038a39a38bd708a67ee2015fa1a862e8fcaf2d73a034bb993`.
Each successful checkpoint checks four guest panels; the other three ports must
remain neutral. Nonzero injection ports and public analog/trigger requests were
rejected and checked for preserved state. GC analog/trigger injection, Wii
IR/extensions, physical hardware and expanded lifecycle qualification remain
outside these passes.

Expansion evidence/identities: `qualified-expansion-identities.json` under the
local evidence root. The DS/GBA results include the exact MCP, supervisor,
core/profile and both worker-source SHA256 identities. Portable installation
receipts and source-build logs are in `setup/`; these are separate from live
proof. The rest of the canonical system catalog still needs the ports and
SDK/runtime verification listed in `_tests/input-lab/README.md`.

Guided native UI, ordered bounded history/overflow, full per-device capability
labels, keyboard/pointer/multitouch, pressure extensions, expanded lifecycle and
cancellation-terminal assertions, and full native Compose build-to-live pipelines
remain unfinished. Existing native programs are useful live input viewers and
guest witnesses, not the complete comprehensive suite. No all-platform,
all-peripheral, retail-game, exact-step or physical-hardware pass is claimed.

Five read-only simplification lenses examined the initial code. Their concrete
cleanup and record-drawing findings were fixed; cleanup regressions failed first
and then passed. This does not stand in for final shipping code review of the
entire unfinished all-platform implementation.

## Fresh screenshot run and GBA presentation correction

The requested fresh run is recorded at
`C:/Users/Boolean/AppData/Local/Temp/emucap-input-lab/requested-rerun-20261104-210800/summary.md`.
All nine configurations passed 695 guest-state checkpoints and completed managed
stop. Screenshot inspection exposed a separate GBA visual failure: telemetry
passed while the title/control grid was blank. Direct redraw of the visible
mode-3 framebuffer raced scanout. The GBA fixture now renders to a 76,800-byte
EWRAM buffer and copies complete RGB555 pixels with DMA at VBlank. No palette or
capture resampling change was needed.

`require_handheld_ui` now rejects captures without visible title/sample labels;
its regression proves valid telemetry alone cannot hide a blank viewer. The
old GBA combined capture fails this new check. Ten host tests pass. Both shared
handheld targets rebuilt with warnings as errors; fresh DS/GBA live runs pass
49/37 checkpoints with the UI check on every accepted capture. New build IDs:
GBA `e7aa0eb6a8beff41833dafb2caaea6ef`, DS
`1654adc0844942755edd14a83909dc11`. Their fixtures are `gba-stable-build` and
`nds-shared-build`, and final evidence is `mgba-stable` and `melonds-stable`
under that run directory. Earlier GBA input-only passes are not visual proof.

The run includes original neutral/held/released PNGs, decoded state JSON,
checksums, source/build manifests and a screenshot bundle with artwork credits.
Physical GBA scanout remains unqualified; the correction was built and observed
in mGBA's software core. No new Rust/native-adapter code changed for this fix.

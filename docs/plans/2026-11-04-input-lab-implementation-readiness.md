# Input Lab implementation readiness

Historical intake: gyro/motion was subsequently removed by user direction.
Native execution now follows `_tests/input-lab/CONTRACT.md`; current implementation,
evidence boundaries and remaining catalog ports are tracked in
`_tests/input-lab/README.md`. The findings below describe the earlier intake.

Source design: `docs/plans/2026-11-04-input-lab-design.md`.
The `ce-work` intake on 2026-11-04 found that this is a product/visual contract,
not yet an executable all-platform implementation plan. No native Input Lab code
has been implemented or built by this intake. Existing prototype and credits
files are preserved.

## Verified repository prerequisites

`src/bin/emucap-mcp/launch/system.rs` defines normalized system IDs:
`snes, gamegear, gb, gbc, gba, nes, saturn, psx, pce, pcfx, md, wswan, ngp,
pc98, neogeo_mvs, neogeo_aes, neogeo_cd, n64, msx, msx1, msx2, msx2p, dc,
nds, psp, ps2, gamecube, wii, xbox, 3ds, switch, switch2`.

Fixture metadata must also preserve actual machine variants: SMS aliases route
through `gamegear`; WonderSwan Color through `wswan`; NGP Color through `ngp`.
The alias `msx2+` normalizes differently from canonical `msx2p`; do not use host
normalization alone as a guest machine identity.

Persistent input takes a complete button/axis state and omitted axes become
neutral. `src/live/controller_input.rs` validates runtime-advertised axis names
and ranges. There is no universal sign, range, button list shape or port list.
Examples:

| Adapter | Existing input limitation / mapping |
| --- | --- |
| Azahar | Port 0, 14 buttons, four signed axes; Y positive down; single 320x240 touch |
| Eden/Ryubing | Port 0, four signed axes, single 1280x720 touch with explicit fork bounds; no timed input |
| N64 | Port 0, axes -128..127, Y positive up; stick direction aliases differ from D-pad |
| xemu | Port 0, signed sticks, triggers 0..32767; trigger aliases conflict with explicit trigger axes |
| openMSX | Port 0 limited keyboard keys, joystick ports 1/2; full keyboard matrix not injected |
| DS | Persistent input port 0 |
| PSP | Persistent combinations supported; timed press path allows one button |
| PS2 | Current persistent path is button-mask based; no universal analog/pressure contract |

`src/live/link.rs` has a single-contact port-0 touchscreen contract. Multi-touch
is therefore a separate schema/adapter unit, not something homebrew alone enables.

## Motion prerequisite

No motion injection/readback contract was found in current Rust capability
surfaces or the common Eden/Ryubing endpoint. Azahar's
`adapters/azahar/bridge.py` explicitly sets `citra_enable_motion=disabled`.
Native guest sensor sampling and host motion injection are different units.
Automated gyro qualification cannot be accepted until a versioned capability,
units/frame/sensor identity, input schema and genuine source-side hook exist.
An inert zero vector is not valid gyro proof. Physical readback may be tested
manually where hardware and a native port exist, with manual-only evidence.

## Locally present SDKs (filesystem/source evidence only)

`B:/tools/devkitPro` contains devkitARM, devkitA64, devkitPPC, libctru, libnx,
libnds, libgba/libtonc and libogc, with examples and packaging tools.

- Switch: existing `build_fixture.py`, `switch.c`, libnx framebuffer/pad/touch
  path; `hidGetSixAxisSensorHandles`, `hidStartSixAxisSensor`,
  `hidGetSixAxisSensorStates`. Verify units/frame/validity before rate conversion.
- 3DS: existing builder and `ctr.c`; rotated BGR screen layout needs its own
  renderer backend. Gyro activation, read and raw-to-dps coefficient APIs exist.
  `angularRate` member declaration order is **x,z,y**, not x,y,z. Check activation
  results; initialize C-stick service explicitly where supported.
- DS: libnds scan/held/down/up/touch/VBlank APIs and ARM9 build rules exist.
  Complete ARM7 packaging and two-screen framebuffer/tile setup remain to verify.
- GBA: libraries/examples exist; exact raster/keypad/cart build remains to verify.
- GameCube: PAD buttons, both sticks and triggers; VIDEO/XFB console patterns.
  XFB pixel layout differs from Switch/3DS and needs its own backend.
- Wii: WPAD buttons/IR/accel/orientation, expansions and MotionPlus raw fields.
  MotionPlus scale/fast-mode/validity must be verified separately from accel tilt.
- Switch 2: preserve `build_ounce_fixture.py`'s separate pinned libnx-ounce,
  reviewed archive hash, Ounce metadata extension and explicit guest memory config.

The existing Wii pacing builder uses `docker run`; do not execute it unchanged.
Any new Docker build must use a committed Compose file, named containers and
host-folder bind mounts.

The GB/GBC fixture currently requires a lawful local cartridge header source;
no such input was selected by this intake. Do not obtain a commercial ROM to
make this gate pass. Existing GB/NES/GBA/MSX fixtures are limited pacing programs,
not existing comprehensive Input Lab ports.

## Required executable units before all-platform acceptance

1. Shared bounded native observation record, explicit validity, sequence/overflow,
   native values and independent host decoder/oracle. Prove capacity and decoding
   at 160x144, including maximum motion payload, before freezing the format.
2. Shared native raster/font layer with platform-specific framebuffer writers;
   build-time conversion and license retention for the selected input-viewer
   artwork. The SVG web specimen is not itself a native renderer.
3. Switch/3DS guest programs using real pad/touch/sensor APIs and checked service
   lifecycle. Build, boot and input qualification are separate gates.
4. DS/GBA/GameCube/Wii programs using their actual device APIs and packaging,
   then GB/NES and remaining catalog toolchain ports. Establish toolchain pins,
   artifact formats, permitted SDKs, licenses and per-device mappings for every
   remaining system rather than guessing portable APIs.
5. Motion capability/schema and per-emulator source hooks for systems where
   automated gyro injection is intended. Unsupported systems stay explicit.
6. Per-adapter input-vector generation from connected capabilities, full bitset
   comparison, signed/magnitude/axis-isolation checks and expected release states.
   Capture terminal cancellation response by request ID; never discard it while
   waiting for a different request.
7. Mutations for swapped bits/axes/ports, scaling, stale/missing records, missing
   releases and wrong cancellation terminals, plus a complete committed Compose
   build-to-live run with fresh evidence. Preserve failed attempts and cleanup.

## Readiness decision

The design remains insufficient to execute the **entire all-platform suite**:
record capacity, remaining toolchain/device mappings and motion schema/hooks
are material prerequisites rather than cosmetic details. `ce-work` input triage
requires `ce-plan` enrichment for a Product Contract without sufficient
implementation direction. Enrichment must turn the units above into concrete
owned file sets, dependency order, source-grounded API decisions and executable
verification before an all-platform implementation run is called ready.

No implementation, cross-build, emulator run or gyro support is claimed by this
read-only intake. No unrelated edits, `3ds_flutter` changes or publication occurred.

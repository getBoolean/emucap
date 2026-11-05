# emucap Input Lab

Status: product and visual design; native port feasibility is not yet qualified.

Visual specimen: `docs/design/input-lab-preview.html` (simulated data, no emulator
connection). Controller, Touch and Coverage tabs illustrate the proposed interface.
The machine-readable strip is decorative in this specimen, not its final encoding.

Document review: local coherence and feasibility reviews returned no findings.
This is requirements-level review, not toolchain or native-build verification.

## Goal

Create original, lawful homebrew for every system in emucap's supported-system
catalog. A person should immediately see what the guest receives; an automated
runner should independently compare those observations with commanded input.
Passing one platform, peripheral, renderer or emulator fork does not qualify another.

The suite is named **Input Lab**. It is a family of native programs sharing a test
specification, visual vocabulary and observation format, not one universal ROM.
No Dart or Flutter dependency and no changes to `3ds_flutter` are required.

Gyroscope and motion testing are excluded by user direction (2026-11-04).

## Product contract

- Live view works with real physical input and with emucap injection.
- Automation covers every advertised input control and controller port, including
  controls absent from the current A/positive-left-X witness.
- Guest-observed raw values are the authority. Commanded values are separately
  labeled and must never be copied into the observed panel or telemetry.
- Required checks have explicit `not-run`, `running`, `pass`, `fail`, `blocked`
  or `unsupported` states. Unsupported controls never add to the pass count.
- Manual observations and machine-verified checks have separate completion counts.
- Builds, synthetic tests, emulator live tests and physical hardware tests are
  separate evidence classes. No promise of deterministic frame stepping.
- A capability exists on three independent axes: physical system, guest port and
  connected emulator adapter. The UI explains which axis prevents a test.

## Visual direction

Use a quiet instrument-panel style: near-black navy background, light labels,
cyan live observations, violet expected targets, green labeled PASS, amber
BLOCKED and red FAIL. Shape, icon and text reinforce every status; color alone
never carries meaning. Use explicitly licensed artwork designed for input viewers
where available, preserving its notices, provenance and required acknowledgments.
The Pro Controller specimen uses shmove's GamepadViewer skin from Open Joystick
Display; see `docs/design/assets/procon/provenance.json` and `COPYRIGHT.md`.
Do not substitute unlicensed commercial renders or bundle proprietary fonts.
Use an original or explicitly redistributable bitmap font with its notice.

The primary 1280x720 layout:

1. Header: Input Lab, platform, controller type and selected port, LIVE/GUIDED,
   guest sample/frame counter and fixture build short ID.
2. Main left: platform-accurate controller diagram with labeled controls. An
   observed button fills cyan immediately; an expected control has a violet
   outline. Unexpected activity gets a red outline without hiding its raw value.
3. Main right: two stick plots with crosshairs, current coordinates, short fading
   trails and separately drawn expected targets. Trigger bars show raw values,
   normalized values and endpoint tolerances. Missing controls are omitted here
   and listed as unsupported in the capability page.
4. Lower panel: active guided instruction, expected/observed values, release
   requirement and per-check result. A failure remains visible until acknowledged.
5. Footer: recent press/release events, sequence number and a small machine-readable
   observation strip. The observation strip is data, not a decorative progress bar.

Input visualization updates at the first completed guest render after sampling;
there is no easing of measured values. Optional trails and status transitions can
be disabled. A slow guest must never fabricate intermediate input samples.

### Views

- **Live:** free exploration, per-control raw/normalized values and down/pressed/
  released states. No automatic pass claims.
- **Guided:** one instruction at a time; neutral -> apply -> hold -> release ->
  verify. Shows missing checks, exact mismatch and last correct observation.
- **History:** bounded ring of transitions and sampled changes; input state,
  guest sample sequence and overflow count. An overflow invalidates tests that
  require complete event history.
- **Touch/pointer:** grid, crosshair, current coordinates, contact IDs, path,
  buttons and contact count; draw both logical bounds and any adapter inset.
- **Coverage:** system/peripheral/port matrix and separate human/machine results.
- **Output devices:** optional rumble/LED requests and human confirmation. An input
  readback or successful API call cannot prove physical vibration or illumination.

### Display adaptations

- 3DS: top 400x240 controller/status; bottom 320x240 touch canvas. Each screen
  carries a screen ID and sample sequence so composite capture errors are visible.
- DS: top 256x192 controller/status; bottom 256x192 touch. Do not reuse 3DS geometry.
- 160x144 Game Boy: high-contrast monochrome-compatible button grid and a large
  current instruction; history and coverage are separate pages. No tiny dashboard.
- Other low-resolution systems: tile/sprite UI in native legal video modes, integer
  pixel positioning, bounded palettes and safe margins. Wide labels abbreviate
  with a legend rather than shrinking until unreadable.
- TV systems: overscan-safe layout, no diagnostic datum solely at an extreme edge;
  optional geometry screen before coordinate tests. Touch itself still tests edges.
- Desktop-style systems: keyboard matrix and pointer pane replace gamepad artwork.
  Preserve machine-specific key labels and distinguish logical key from text input.

Navigation must not consume controls under test. Guided runs enter a fixed test
page and lock navigation until a neutral transition. A configurable long exit
chord is disabled during its constituent button checks. Host stop remains the
automation escape route; no single Start/Plus press immediately exits the witness.

## Comprehensive input specification

### Digital controls

For every advertised button, key and direction: neutral baseline, isolated press,
multi-sample hold, release, rapid repeat, and a return to neutral. Verify the
entire observed bitset, not just the expected bit. Include swapped/missing bits,
stuck buttons, unwanted neighbors and duplicate rising/falling events.

Test representative pairs/chords, all-buttons where legal, diagonal directions,
opposite directions and device-specific mode buttons. Opposite-direction policy
must be declared (allow, prioritize, neutralize or reject), never assumed universal.
Exhaustive combinations are optional extended tests, not a prerequisite to the
normal suite. Reserved OS/emulator buttons are reported explicitly.

### Analog sticks and triggers

Test every axis separately at zero, positive/negative quarter, half and endpoints;
all cardinal and diagonal vectors; circular versus square clamping; inversion;
cross-axis leakage; both sticks simultaneously; long hold; and full release.
Observe raw integers and normalized values with a declared conversion and bounded
rounding tolerance. `requested 24000 -> observed any positive value` is insufficient.

Dead zones, quantization and asymmetric ranges are profile data. Do not calibrate
the expected range from the same broken sample being tested. Physical-controller
calibration is a separate manual session, preserving the original measurements.
Analog triggers additionally test independent travel, simultaneous activation,
and digital click threshold when a device actually exposes one.

### Touch, pointer and keyboard

Touch covers min/max and the other two corners, center, edge midpoints, off-center
points that detect X/Y swap, drags, repeated taps, stationary holds and release.
Test each advertised contact and multi-contact transitions only where supported.
Check contact start/end and no ghost contact after release. Out-of-range host
requests must fail without changing an existing held contact; the guest confirms it.

Pointer tests cover absolute/relative semantics separately, both movement signs,
button holds/chords/releases, wheel signs and advertised scaling/clamping.
Keyboard tests cover the advertised matrix, modifiers, simultaneous keys, held
keys, releases and repeat behavior. Text entry is tested separately if available.

### Ports, lifecycle and cancellation

Run each advertised port independently; then different simultaneous states on
multiple ports to expose cross-routing. Test advertised connect/disconnect and
controller-type changes without assuming every platform supports hotplug.

Exercise cancellation of an admitted frame wait while input remains held. Assert
the exact original request's terminal outcome and bounded completion, then verify
unrelated input is unchanged. Queue unmatched MCP responses by ID rather than
discarding them. Do not infer successful cancellation merely from a later status.

Add independent scenarios for disconnect cleanup, reconnect behavior, process loss,
stop during capture, capture timeout/recovery and failed replacement. Each scenario
specifies its expected cleanup policy. Unsupported lifecycle operations are blocked
or unsupported cells; ordinary launch/stop never substitutes for exceptional tests.

Timing is measured in guest samples plus observed host intervals. Report missed
samples, queue overflow and observed overshoot. Exact emulated-frame timing is
qualified only for adapters that advertise and prove it. Presentation stability
and cached paused capture do not establish CPU halt.

## Platform coverage and port admission

The following is the required catalog, not a claim that toolchains or ROM builds
for every row have been verified. Implementation must inventory actual emucap
system IDs, aliases, advertised ports, devices and input bounds against this list.

| Native port group | Required target variants | Primary input views |
| --- | --- | --- |
| Nintendo handhelds | GB, GBC, GBA, DS, 3DS | Digital; DS/3DS touch; 3DS advertised analog |
| Nintendo consoles | NES, SNES, N64, GameCube, Wii | Digital; native analog/triggers; Wii device profiles separately |
| Horizon | Switch 1; separate Ounce Switch 2 build | Controller, sticks, touch and advertised ports |
| Sega | Master System, Game Gear, Mega Drive/Genesis, Saturn, Dreamcast | Digital; device-specific analog/triggers |
| Sony | PlayStation, PS2, PSP | Digital; device modes and available analog/pressure controls |
| NEC | PC Engine, PC-FX, PC-98 | Gamepad or keyboard/pointer according to actual device |
| SNK | Neo Geo Pocket/Color; MVS/AES/CD | Digital, ports and arcade/service inputs where advertised |
| Bandai | WonderSwan/Color | Both orientation control groups and orientation-aware labels |
| MSX | MSX1, MSX2, MSX2+ | Keyboard, joystick and advertised pointing devices |
| Xbox | Original Xbox | Digital, sticks, analog controls and available ports |

Every device variant gets its own profile: e.g. PS digital versus analog pad,
Wii Remote versus Classic/GameCube controls, 3/6-button Sega pads, N64 accessories.
IR, pressure, light guns, microphone, rumble and extensions require an
actual guest read/output path and an emulator capability. Design room for them;
never silently mark them tested through a standard gamepad.

Before implementation of each row, verify maintained open toolchain, artifact
format, SDK license, available guest APIs, emulator boot requirements and build
recipe. Firmware-dependent ports may be blocked without lawful local prerequisites.
No commercial SDK, games, downloaded firmware or keys. Switch 2 reuses the existing
original Ounce witness work and explicit composite-media approval boundary; Switch
1 success must never qualify its separate binary or runtime.

## Architecture and observation contract

Share a declarative suite and vectors on the host, not one rendering/runtime
dependency across incompatible CPUs. Each native port implements sampling,
canonical control mapping, rendering and telemetry encoding. Generated headers
and compact data tables may share control IDs and UI assets; small ports can
implement the same contract in assembly or a limited C subset.

The host owns expected commands and the oracle. The guest owns observed state.
Standalone manual mode requires no RPC server or injected test results. In guided
mode, selected case IDs drive instructions; independent host comparison decides
automated pass. Guest self-checks must be labeled separately.

A versioned observation record includes schema, fixture/build ID, platform and
device IDs, port, guest sample/render sequences, full digital bitsets, all raw
axes, contact state, last transition sequences, overflow flag and checksum.
Encode complete records across indexed pages on small screens; never combine
different sequences into one snapshot. Repeat record headers/checksum on each
page; handle sequence rollover explicitly. Keep platform-native values alongside
canonical values so a mapping defect can be localized.

Use screenshot-decodable high-contrast cells for a universal channel, with finder
marks, version, page ID, dimensions and error detection. Exact encoding, payload
capacity and readback strategy need a feasibility spike at 160x144 before freezing
the protocol. Integer scale and coordinate bounds are validated; filtered, cropped,
corrupt or partial records fail closed. A strip checksum detects corruption; it
does not cryptographically attest emulator truth.

Prefer an independently specified guest memory/log channel where the adapter
exposes one, cross-checking it against visible observations. No memory-read support
is assumed. A page-selection control is excluded from measurement during navigation,
then released before sampling resumes. Avoid a hidden dependency on an exact-step
API to read multi-page records.

Randomized host vectors, fresh sample progression and immutable per-build/run
identity reduce accidental stale evidence. Persist random seeds and exact command
sequences. A host-painted overlay cannot supply observed values or pass criteria.

## Evidence and verification contract

Per exact emulator/build/system/device/port/renderer/config cell, record original
fixture source and artifact hashes, toolchain/SDK pins and notices, emulator and
adapter identities, suite version, seed, expected commands, request IDs and terminal
results, decoded observations, PNGs, monotonic timestamps and cleanup evidence.
Keep all attempts; never overwrite an earlier failed run with its retry.

The runner must emit independent counters for required, passed, failed, blocked,
unsupported and not-run cases, plus manual-only checks. Any required missing case,
decoder error, invalid record or overflow makes the cell incomplete or failed.
Compare host capability declarations with the fixture profile before mutation.

Verification layers:

1. Pure encoder/decoder fixtures at native resolutions, corruption, scaling,
   stale sequence, rollover, truncated and multi-page mismatch rejection.
2. Oracle fault injection: swapped buttons/axes/ports, inversion, stuck input,
   wrong magnitude, missing release, dropped transition, ghost touch, stale frames
   and wrong cancellation terminal. Each defect must produce the intended failure.
3. Cross-build each native port; compile/boot-only is never input qualification.
4. Live end-to-end tests through emucap against the source-built homebrew, with
   human visual inspection of representative images and exact input assertions.
5. Optional physical hardware sessions recorded separately from emulator evidence.

All Docker use is through committed Compose files, named containers and explicit
host-folder mounts. Require one complete committed pipeline run from build through
guest checks and cleanup with fresh evidence before claiming reproducibility.
Dependency caches may be reused with recorded pins; manual spliced build/guest runs
remain useful component evidence but do not close that pipeline gate.

## Delivery slices and acceptance

1. Freeze the platform/device inventory and a requirements-to-case matrix. No
   all-platform completion claim while any catalog row lacks a disposition.
2. Spike the smallest display's observation format and dual-screen layouts. Review
   readable native-resolution captures before expanding the UI assets.
3. First native ports: Switch 1/Ryubing and Eden, 3DS/Azahar, DS and one 8-bit
   platform. Validate shared semantics and platform differences before mass ports.
4. Add original Ounce Switch 2 build and exact fork/config cells independently.
5. Expand across the catalog in toolchain groups, verifying device-specific ports.
6. Run mutation tests, clean full Compose pipelines, live matrix and final review.

This design is ready for feasibility and implementation planning, not yet for
claiming an all-platform executable implementation. Open implementation gates:
toolchain/API/license inventory for remaining systems; low-resolution record
capacity/paging; per-device raw ranges and adapter normalization; unsupported
peripheral handling. Those gates must produce evidence, not guessed SDK choices.

## Local grounding

- `README.md`: current system catalog (supplemented by the implemented Ryubing port).
- `_tests/live/emulator-family/{switch.c,ctr.c,qualify.py}`: existing original pixel
  witnesses, hold/release/touch and lifecycle test patterns and current coverage gaps.
- `_tests/live/mesen2/support.py`: response handling requiring per-request queuing
  before rigorous cancellation terminal validation.
- `docs/ryubing-qualification.md`: exact support/evidence boundaries and the gap
  between component validation and a complete committed pipeline run.

UI skill search returned generic web/marketing guidance; that layout was rejected
as unsuitable for native diagnostics. The design instead applies its relevant
high-contrast, explicit-feedback and uncluttered-layout principles. No external
SDK feasibility or toolchain recommendation is asserted by this design.

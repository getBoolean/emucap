# Ryubing integration and qualification

Ryubing is integrated as `ryujinx-family-native`, independently of the shared
Eden-family source adapter. Both use emucap's authenticated native transport,
capability contracts and managed launch supervision. Existing Switch defaults
remain Eden; select `emulator.fork = "ryubing"` explicitly. Compatible forks can
provide their own pinned profile, source patch and executable.

The maintained source is `https://git.ryujinx.app/projects/Ryubing.git`, revision
`a61a42681119bf15fe8f3297677ae48bda83e70f`. This source implements Switch 1.
Recognition of newer controllers does not establish Switch 2 machine support.
Its source recipe currently supports Windows/Linux x86_64 and requires .NET 10
SDK for building, .NET 10 runtime for execution, and the complete output folder.
No emulator or .NET runtime was added to the core release package.

## Implemented operations

- Managed launch/stop, matching embedded build profile, renderer/content identity,
  isolated generation root and curated GPU selection configuration.
- Persistent controller buttons/sticks and one touchscreen contact, including
  Start/held/End reports over 1280×720 coordinates. Unsupported Home/Capture fail.
- Actual renderer capture with RGBA/BGRA and axis-flip normalization across the
  native C ABI. The compiled frontend verifies the native library digest.
- Observed presentation waits/cancellation. These count actual Vulkan present or
  OpenGL swap events, with overshoot; they do not implement deterministic stepping.
- Horizon pause/resume with verified state readback. Paused screenshot returns
  the cached last-completed image, with no implicit resume or fresh guest sampling.

The managed source hooks own persistent input across polling ticks. Renderer
callbacks copy pinned data before returning. Shutdown releases native effects
before input disposal and retains delegates/native handle through GPU teardown.
Managed stop qualification verifies process termination via the supervisor;
separate native-close probes exercise ordinary SDL close from running and paused
states. This does not establish teardown with a capture callback in flight.

## Startup failures found and corrected

An actual detached Windows launch failed with `ConsolePal.set_Title: The handle
is invalid`. Managed execution now avoids console title/color operations while
retaining redirected logs. A subsequent complete live control run passed, then
a fresh-root repeat failed with `KeyNotFoundException: BuiltInSystem` from the
NGC service's content lookup. Content indexes are now loaded synchronously before
service threads start; the later device-specific content initialization remains.
Missing content retains the existing empty lookup / `TargetNotFound` result.
No firmware assets, keys, service suppression or fabricated success were added.

The earlier passing run is historical evidence for its build. Qualification of
the final startup-order correction uses separate clean-root runs.

Review also corrected renderer-thread retention for ordinary launches,
CPU-targeted pause/resume rejection, hidden-window selection, content-pinned JSON
headers and explicit custom-fork launch documentation. Paused PNG equality is
only a cache check: the harness separately samples native presentation progress,
rejects running waits while paused and requires two advancing fresh captures
after resume. Guest CPU halt is explicitly unqualified by cached images.

Native Windows close testing found that SDL events were not being polled.
A bounded owner-thread `PollEventsDispatcher` now handles polling independently
of the synchronous main-thread dispatcher required by Vulkan surface creation.
An intermediate attempt incorrectly made that generic dispatcher asynchronous;
its Vulkan failures were rejected, then the separated dispatch implementation
was rebuilt and qualified. Native close waits for the exact owned process to
exit with code zero; it cannot pass merely because supervisor cleanup killed it.

## Local verification

Host: Windows x86_64, Intel UHD Graphics 630, Intel Vulkan 1.3.215 / driver
31.0.101.2140. The source built with .NET SDK 10.0.403; runtime 10.0.14 was observed
in the emulator log. Native C ABI built with MinGW GCC 12 using C++20.

The pristine source build passed before integration. Full patched publish and
embedded-profile probe passed after the corrections. Compiler/trim/Avalonia
warnings remain warnings; build success alone is not guest proof.

- `cargo test --locked --release --all-targets -- --test-threads=1`:
  1,963 passed, four ignored, zero failures.
- `cargo clippy --locked --release --all-targets -- -D warnings`: passed.
- Nine Windows fast lanes: passed, including an actual DLL load and authenticated
  loopback C ABI control with synthetic hooks. This is protocol evidence only.
- Recipe tests: four passed. Artifact/failure admission: twelve passed. Guest
  witness admission: fourteen passed. Core package boundary tests: five passed.
- Actual C ABI malformed profiles with matching sidecar/options are rejected;
  pause/capture/input/touch/stop synthetic tests passed on the built native DLL.

Live uses original CC0 homebrew from `_tests/live/emulator-family/switch.c`, built
with devkitPro and standard NACP metadata generated by `nacptool` and embedded by
`elf2nro`. It requires no commercial content, firmware or keys. The fixture NRO
SHA-256 is `07b7857557fe00db9d5b621dcc07005c169c3237fc5be6ee69aacaf662309f1b`.

The pre-review startup-fix build4 patch digest was
`5070c78d3b63d38fa5d1e80b1dc970bf0ef3b5709a3410b3feee07ef1ea31311`.
Its managed `Ryujinx.dll` SHA-256 was
`ff2c81701a307038a57421c472af44d016eaadfa28cc1269f245d596f4a66fd3`;
`Ryujinx.HLE.dll` is
`8fc0a0eb2d9891d8d5c42355b3fa55dd8bdb714845cc75f1bfbf984d015200fa`;
`emucap-native.dll` is
`eb83d17c67e319009712c4cb48c73674c1eee50fbe7a55e68e97ae490e139685`.
The apphost executable alone does not identify the managed program. The live
harness records the managed modules, runtime configuration and native bridge too.

Evidence is local under `C:/Users/Boolean/AppData/Local/Temp/`:
`emucap-ryubing-managed-build4.log`, `emucap-ryubing-ci-fast/`,
`emucap-ryubing-all-targets.log` and `emucap-ryubing-clippy.log`.
The complete built frontend is `emucap-ryubing-build/bin/`.

Three independent startup-fix build4 runs passed: `emucap-ryubing-live-004/`,
`emucap-ryubing-live-005/` and `emucap-ryubing-live-006/`. Each contains
`result.json`, tool results, native logs and actual guest PNGs. Each proves
changing guest-visible counters, A/stick input and release, full-area touch
corners/center and release, active wait cancellation preserving held input,
rejected profile replacement preserving the generation, native paused-state
readback, cached paused images, advancing guest pixels after resume and verified
process exit on managed stop. Supervisor stop used `taskkill`, recorded explicitly
in the result. These are homebrew input witnesses, not retail-game coverage.

The shared-bridge Eden regression was rebuilt and passed actual Switch 1 guest
control in `emucap-ryubing-eden-regression-002/`. An earlier test mistakenly used
the Switch 2 memory layout for Switch 1 and failed; this was not a passing run.
The successful regression selects Intel Vulkan with the default memory layout.

## Reviewed build8

The final pinned header participates in patch digest
`8cc619e18214d26ccf7509b24d0f34b6ae36218fc5bb6b21075c0e3a7cf6cc85`.
Build8 module SHA-256 values were:

| Module | SHA-256 |
| --- | --- |
| `Ryujinx.dll` | `2b0976aea6eb5c8e6153943013553645b0d34b4e8612ea0e0300d2bd0b79918b` |
| `Ryujinx.HLE.dll` | `8fc0a0eb2d9891d8d5c42355b3fa55dd8bdb714845cc75f1bfbf984d015200fa` |
| `Ryujinx.SDL3.Common.dll` | `693b34621b7293da284807b928715a5e6c3f73e7a8708f6ddb451ebd60f2fc41` |
| `emucap-native.dll` | `39b1d6de249966c70ebe85d3065b295f654ae6b9b59fef2186d1abce2e3ad1fc` |

`emucap-ryubing-managed-build8.log` records successful full publication and
embedded-profile probing. `emucap-ryubing-final-fast/fast-results.json` records
all nine passing synthetic lanes after the CPU-target correction. The old DLL
failed the new CPU-targeted pause regression; the corrected built DLL passes.

These final-build Intel Vulkan runs passed the full guest control harness:

| Evidence directory | Additional proof |
| --- | --- |
| `emucap-ryubing-final-vulkan-close/` | Visible window; native close from running exits zero |
| `emucap-ryubing-final-vulkan-paused-close/` | Visible window; native close while paused exits zero |
| `emucap-ryubing-final-vulkan-hidden/` | Six owned windows, none visible; full guest capture/control still advances |
| `emucap-ryubing-final-opengl-hidden/` | AMD RX 7900 XT OpenGL 4.6; eight owned windows, none visible; full control/capture passes |

All paths are under the local temporary directory noted above. Paused native
presentation counters remained constant during the one-second samples; this is
observed presentation stability, not proof that every emulated CPU stopped.
Paused guest-state sampling remains explicitly unqualified in `result.json`.
The latest common bridge also rebuilt and passed an actual Eden control witness
in `emucap-ryubing-final-eden-regression/`.

Earlier build7 OpenGL probes `emucap-ryubing-live-opengl-001/` and
`emucap-ryubing-live-opengl-paused-close/` also verified native exit zero from
running and paused states. Build8 adds the corresponding Vulkan close proof and
current hidden OpenGL control proof. Intermediate failed Vulkan/close probes are
not passing qualification records.

## Portable path follow-up and Compose validation

The Linux GCC 13 strict build rejected deprecated `std::filesystem::u8path`.
The shared bridge now constructs C++20 UTF-8 paths without suppressing warnings.
Actual Windows and Linux C ABI tests use a Unicode root and verify profile-file
loading, root identity and controls. Pending-capture stop coverage now requires
proof that the capture was admitted before cleanup.

The updated Windows build9 passed publication/profile probing and a fresh full
hidden Vulkan guest run in `emucap-ryubing-portable-windows-hidden/`. Its patch
digest is `40d8ff4ff1cc6b8a4af490d5b2fe298215ea7bfdf38b9e3c4804d349f9238d4d`;
`Ryujinx.dll` is `6658645324842c4bc3554d920f10a71e8fcec50932a2e11155e7833b87e9a925`,
and `emucap-native.dll` is
`6ea3b5a5be540fb3edc94eb2101f9983c57fdc783297209a6db18153be049de7`.

[Compose validation](../_tests/emulator-bridges/docker/README.md) uses explicitly
named services and existing host-folder bind mounts. The checkout, upstream
source and fixture are read-only; source/build trees, dependency downloads,
caches and outputs stay in separate mounted folders. Image metadata and actual
container mounts were checked: no anonymous/named data volumes are introduced.
The state drive had over 800 GiB free before these builds.

All nine Linux fast lanes passed through `compose exec -T`, including eighteen
artifact-admission tests. The actual Ounce builder manifest is now accepted,
both ExeFS members and config/descriptor/source hashes are checked, and Switch 2
live CI requires an explicit reviewed-media approval input. A Switch NRO cannot
qualify Switch 2. These are admission/CI checks, not a remote live CI result.

The full Linux Ryubing frontend published and passed its compiled-profile probe
with SDK 10.0.403, runtime 10.0.14 and GCC 13.3.0. Its source patch digest matches
the portable Windows build; target is `x86_64-unknown-linux-gnu`.
Linux `Ryujinx.dll` is
`c30152cc0d4b488815f99bdbadca33ff6d8dee326753110aafd8edfab4c2bbbd`;
`libemucap-native.so` is
`85ec9909751df676ec33834044f21aeedb15413494f93983a44e9cafc74fbf61`.
This is frontend-build and native ABI proof; Linux guest execution is a separate
qualification step.

The subsequent Compose guest check exposed an upstream NRO loader opening its
input with implicit read/write access. A read-only fixture bind was rejected
before bridge readiness. The maintained source patch now requests
`FileAccess.Read`; the fixture bind remains read-only. A fresh Windows hidden
Vulkan control run after that change passed at
`C:/Users/Boolean/AppData/Local/Temp/emucap-ryubing-readonly-windows-hidden/result.json`.
Its managed frontend hash is
`64c386e730cdbfd02c9156bfd5d1ad084e6f9646088d6c282621f3abd2a88a77`.
This correction followed the review receipt described below; that receipt is
not a new independent review of the correction.

The default Linux `HostMappedUnsafe` mode then aborted during homebrew loading,
including in a standalone launch. The same frontend loaded and rendered the
witness using upstream's `SoftwarePageTable` option. Managed config now accepts
an explicit `memory_manager_mode` whitelist; no emulator default was changed.
The Compose and Linux CI lanes select that mode and set
`DOTNET_EnableAlternateStackCheck=1`, as the pinned upstream Linux launcher does.
The final patch digest is
`559d29382481a1610965b7c8aae3129cde1147e5572541cac8270bfe90b78167`.
A fresh Windows hidden Vulkan run after this config addition passed at
`C:/Users/Boolean/AppData/Local/Temp/emucap-ryubing-config-windows-hidden/result.json`,
with zero visible windows and unchanged native presentation count while paused.
Its `Ryujinx.dll` hash is
`deab556892a5480bd5b995e17a0b585919767ac4ad269b645d6aa4a271d6eef2`.

Final Linux live control passed under the named Compose container, non-root,
Xvfb and Mesa llvmpipe Vulkan 1.4.318 / Mesa 25.2.8 / LLVM 20.1.2, using the
explicit software-page-table config above. The read-only fixture remained the
same NRO with SHA-256 `07b7857557fe00db9d5b621dcc07005c169c3237fc5be6ee69aacaf662309f1b`.
Evidence is at
`C:/Users/Boolean/AppData/Local/Temp/emucap-ryubing-compose/native/live/guest005/result.json`.
Guest frame 8 had no controls; frame 59 reported button A and stick value 24000;
frame 126 reported both released. Touch center/corners/release checks passed.
Native presentation remained 248 across the one-second paused observation;
fresh resumed captures advanced to guest frame 285. Managed stop verified exit.
This does not independently establish guest CPU halt while using cached capture.
The final Linux `Ryujinx.dll` hash is
`e89e662d73333be75ffb6eb2fa549c885f9a83aa9a5f9d4c8b3c6034ffe93e52`;
MCP hash is `9cf0f1348476108a8fcfb3e286e85c324ffe84ea0cd978ada36d1a83858153d2`.
The full frontend publish and Linux MCP build passed in separate logged steps;
the final guest invocation reused that built MCP after a redundant compile was
stopped. Earlier failed/interrupted attempt logs and their top-level result are
retained; they are not relabeled as successful full-script runs.
A second clean-root Linux run with the virtual display enabled also passed at
`C:/Users/Boolean/AppData/Local/Temp/emucap-ryubing-compose/native/live/guest006/result.json`.
These are two guest-control runs of the final source build, not retail titles.

A focused local follow-up review of the NRO read-access fix, config whitelist
and Linux runner changes found no defects. The artifact/runner suite now has
nineteen passing tests on both Windows and Linux, including required Linux
config/runtime-flag forwarding. It is distinct from the broader receipt below.

The broader current-branch review `20261104-emucap-current` completed all eight
native reviewer lenses with no outstanding findings. It confirmed correction
of the Ounce CI admission issue. Its new independent Claude pass failed with a
provider rate limit and supplied no review result; the earlier completed Claude
review is historical. The new receipt is in the same local review directory
hierarchy as the preceding receipt.

## Limits

Completed code review: `20261104-ryubing-final`, with eight local lenses and a
completed independent Claude pass. Six initial findings were corrected and
independently validated; the final receipt reports zero actionable findings.
The receipt is local at
`C:/Users/Boolean/AppData/Local/Temp/compound-engineering-Boolean/ce-code-review/20261104-ryubing-final/review.json`.

Windows and Linux with the exact homebrew fixture/config above are the local
live qualification scope. Linux source/virtual-display CI and cross-platform
synthetic tests are wired but no remote CI run was performed. Linux default
host-mapped memory remains unqualified. macOS/ARM frontend builds,
teardown with pending capture, capture-timeout recovery, disconnect input
cleanup, other titles and firmware-dependent behavior remain unqualified.
No retail game-compatibility claim is made. Ryubing Switch 2 and exact stepping
are unsupported. Earlier Eden-family AMD surface-query failures remain historical
evidence. A later standalone Win32 WSI probe succeeded on both AMD and Intel;
that does not establish current AMD Vulkan guest compatibility in these emulators.

## Changed paths

Paths added or modified for Ryubing relative to the completed control recovery
commit `8daf7f6`:

```text
.github/workflows/emulator-bridge-validation.yml
AGENT_GUIDE.md
CREDITS.md
FORK.md
NOTICE
README.md
_tests/emulator-bridges/docker/Dockerfile.native
_tests/emulator-bridges/docker/README.md
_tests/emulator-bridges/docker/compose.yml
_tests/emulator-bridges/docker/fast.sh
_tests/emulator-bridges/docker/ryubing.sh
_tests/emulator-bridges/fast.py
_tests/emulator-bridges/live.py
_tests/emulator-bridges/native_build.py
_tests/emulator-bridges/test_failures.py
_tests/emulator-bridges/test_live.py
_tests/live/emulator-family/README.md
_tests/live/emulator-family/build_fixture.py
_tests/live/emulator-family/native_close.py
_tests/live/emulator-family/qualify.py
_tests/live/emulator-family/test_qualify.py
_tests/release/package_core.py
adapters/eden-family/native/EmucapBridge.cpp
adapters/eden-family/native/EmucapBridge.h
adapters/eden-family/tests/bridge_tests.cpp
adapters/ryujinx-family/.gitignore
adapters/ryujinx-family/README.md
adapters/ryujinx-family/build.ps1
adapters/ryujinx-family/build.py
adapters/ryujinx-family/build.sh
adapters/ryujinx-family/managed/EmucapSession.cs
adapters/ryujinx-family/managed/EmucapStartup.cs
adapters/ryujinx-family/native/EmucapNative.cpp
adapters/ryujinx-family/native/EmucapNative.h
adapters/ryujinx-family/patches/ryubing.patch
adapters/ryujinx-family/profiles/ryubing.json
adapters/ryujinx-family/tests/native_abi_test.py
adapters/ryujinx-family/tests/test_build.py
contracts/exceptions.json
docs/emulator-family-qualification.md
docs/plans/2026-11-04-feat-ryubing-support-plan.md
docs/ryubing-qualification.md
src/bin/emucap-mcp/launch/emulator_family.rs
src/bin/emucap-mcp/status.rs
src/bin/emucap-mcp/status_tests.rs
src/contracts_tests.rs
src/emulator_profile.rs
src/emulator_profile_tests.rs
src/launch/emulator_family.rs
src/launch/emulator_family_tests.rs
```

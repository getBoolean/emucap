# Emulator integration validation

Scope: local checkout `B:/dev/GitHub/emucap`, branch
`feat/azahar-libretro-bridge`, compared with `21812b8e3fd37c9cab602ce5a4e607988a4c0cfa`.
This report records the initial completed checkpoint `cfc8b74`. The subsequent
[Ounce fixture and live verification](switch2-ozone-research.md) supersedes its
Switch 2 packaging blocker and adds the follow-up paths listed there.
No push, PR, worktree, commercial asset or `3ds_flutter` edit is part of this work.
The final package's adjacent JSON binds its exact clean source revision; live
witnesses below bind the executable/core/fixture bytes they actually used.

The Eglantine target is **Djihads80/Eglantine `nx2`**,
`c54bc2289bfffda7fa3cc4c3a8cf522d84a10fd4`. It supersedes the original plan's
Selevet target. See [qualification](emulator-family-qualification.md) and
[the plan](plans/2026-11-04-0231-feat-azahar-eden-family-support-plan.md).

## Local checks

| Check | Result |
| --- | --- |
| `cargo fmt --all -- --check`, `git diff --check` | Passed |
| `cargo test --locked --release --all-targets` | **1,956 passed, 4 existing ignored**, 21 test binaries |
| `cargo clippy --locked --release --all-targets -- -D warnings` | Passed |
| Release binaries, default and explicit `x86_64-pc-windows-msvc` | Built; final clean-source package has its own manifest |
| Fast bridge runner | All six lanes passed; compiled/loaded C ABI plus authenticated C++ endpoint |
| Python focused lanes | Azahar 21, Eden build 4, guest admission 6, package 5, artifact admission 7 passed |
| Python compilation | Passed for adapter, witness, CI and package scripts |
| Actionlint 1.7.12 | Both affected workflows passed |
| Extracted Core archive at `6be8911` | Registration, both MCP catalogs/build identity, Azahar host/worker, missing-core rejection and actual CTR guest passed |
| Actual Azahar core | Windows MinGW linked core, exported API/profile match and live CTR/software witness passed |
| Eden, Eden-NX2, Djihads80 Eglantine | Full Windows GNU builds, staged runtime DLLs, exact native profile queries and Switch 1/Vulkan witnesses passed |
| Hosted CI; Linux/macOS full native builds/live guests | Not executed |

The final Rust run is `emucap-final-all-targets-fixed.log`; lint is
`emucap-final-clippy-fixed.log`. Earlier failing runs remain retained. Two test
fixture defects were diagnosed rather than dismissed:

- The cancellation-drain test reproduced failures in the untouched archived
  baseline (7/100) and current source (5/100). Its sockets omitted production's
  `TCP_NODELAY`. Adding that setting, with the same 300 ms deadline and assertions,
  passed **1,000/1,000** repetitions (`emucap-wire-nodelay-repeat.json`).
- Reconnect authentication reproduced the exact missing-launch-ID failure in the
  archived baseline (2/50). `ReconnectAuthEnv` released its mutex before its field
  restored environment variables. Declaring the environment guard before the lock
  keeps restoration inside the critical section; **50/50** repeated five-test
  reconnect groups passed afterward (`emucap-reconnect-fixed-repeat.json`).

The baseline is an untouched `git archive` of the base above, not a worktree or
stash. Its required full suite also passed; the repeated narrow runs establish
the intermittent failures. Production cancellation/authentication logic was not
changed for these two fixture fixes.

The package's explicit UTF-8 Cargo-manifest read fixes a CP932 failure reproduced
in current and baseline source. Five package tests and an extracted archive
passed. The final delivery archive is built from the final clean commit under
`emucap-final-package/`; its adjacent JSON records source revision, binary/resource
hashes and extracted-package validation. Native emulators and Python remain
separate prerequisites.

## Native build evidence

All three Eden-family Windows executables linked and returned compiled profiles
identical to their sidecars. Output is under
`emucap-plan-research/<fork>-gcc16-native-full/bin/`, with source/build receipts
and logs beside those directories. Azahar's real core is
`adapters/azahar/build/azahar_libretro.dll` (ignored build output).

The installed MinGW-w64 10 compiler failed an unmodified Xbyak 7.40.1
`EfficiencyClass` probe. The same probe passed with a task-local WinLibs
GCC 16.2 / MinGW-w64 14 toolchain. Its official archive SHA-256 is
`e74df1e528fe6506646edb1c1b06de3e9a78fbb79b45dad6e284161bba4138fb`.
Builds use four Ninja jobs, two OpenSSL make jobs, `ENABLE_WERROR=OFF` (diagnostics
retained) and `ENABLE_LIBUSB=OFF` (native virtual input remains). No global PATH
or installed toolchain setting changed. Interrupted attempts receive no credit.

Independent unmodified dependency probes established httplib's missing
`GetAddrInfoExCancel` declaration and windres's long-command failure. Windows GNU
defaults now select the supported synchronous resolver and windres temporary
files. Variant builds reuse the exact completed OpenSSL 3.6.2 static prefix via
upstream dependency options; version/link/runtime checks and hashes are retained.

Actual launch initially failed with `0xC0000139` when an older GCC runtime was
found on PATH. The builder now stages available runtimes from the **CMake-selected
compiler**, recognizes upstream `eden-cli.exe`, and probes the staged executable
before publishing a sidecar. The independent before/after runtime-helper proof
and focused regressions cover older PATH and unrelated working-directory DLLs.
All three staged executables also returned matching native profiles with child
PATH restricted to Windows System32. `native-clean-path-proof.json` records
those results and the six adjacent compiler-runtime DLL hashes for each build.

## Actual guest evidence

All paths below are under `C:/Users/Boolean/AppData/Local/Temp/`.

| Cell | Result directory | Verified behavior |
| --- | --- | --- |
| Azahar / CTR / Windows / software / no display | `emucap-live-azahar-007` | Composed 400x480 pixels, guest counter, A/positive left-X hold/release, full 320x240 touch corners/center/release and bottom-screen response; cancellation recovered control in 0.110 s |
| Eden / Switch 1 / Windows / hidden Vulkan | `emucap-live-eden-002` | Guest pixels/counter/input/touch/release; active wait cancellation recovered control in 0.094 s |
| Eden-NX2 / Switch 1 / Windows / hidden Vulkan | `emucap-live-eden-nx2-003` | Same witness; cancellation recovery 0.188 s |
| Djihads80 Eglantine / Switch 1 / Windows / hidden Vulkan | `emucap-live-eglantine-002` | Same witness; cancellation recovery 0.109 s |

Every passing run also proved mismatched-build replacement preserved the connected
generation, cancelled waits preserved unrelated held input, and managed stop
verified owned processes exited. Vulkan host: AMD Radeon RX 7900 XT,
Vulkan 1.4.359 / AMD driver 2.0.416. The Switch sensor's inclusive touch rectangle
is x=15..1264, y=15..704 within logical 1280x720 dimensions. The capability reports
that rectangle, and out-of-rectangle requests reject before mutation. The live
witness rejects (0,0) and verifies the held coordinate did not change.

Shared-schema witness MCP SHA-256:
`ddbf7404a95edbfd94fbb83fac05ece9218c95e43382b45dac1e84c0312d8b6e`.
Azahar core SHA-256:
`915f475a694a948432ebebc365ac223c3fc484cca0c50e407fe8985097e362ce`.
CTR fixture SHA-256:
`c2a3c036df994f751917f37482897e1ed5f7e6dbdc13147d502cdc9a4f0ceaa2`.
Switch fixture SHA-256:
`20e32a4d8f69e1619ebd1a6b7812f6d5c6d1dccc762b243c01b954598631de10`.
Per-fork native executable hashes are in the qualification matrix and each result.

Historical Azahar `006` used the extracted Core package from clean commit
`6be8911`, including packaged worker resources. Archive SHA-256:
`e5765b39b7919cc637a7da2cc0ae16271041c7b92e5a3dcec8e80a00b121e7ea`.
The later `007` run proves the touch-schema extension retained Azahar behavior.
Neither historical package nor current native hashes are silently attributed to
a later binary. Failed harness attempts remain separate failed results.

## Unqualified cells and blockers

- **Switch 2 at the initial checkpoint:** NPDM packaging was blocked. The later
  [Ounce fixture verification](switch2-ozone-research.md) resolves that gate and
  records passing configured homebrew runs in both forks. Broader Switch 2
  compatibility and the documented failing native memory paths remain unqualified.
- **OpenGL:** hidden Eden `003` and NX2 `002` produced all-black PNGs and failed the
  guest-magic assertion. Eden visible `004` failed readiness. Cause unresolved;
  Eglantine OpenGL was not qualified. Do not credit these as passing captures.
- **Partial native startup:** initial Vulkan failures are retained, including an
  observed `VK_ERROR_UNKNOWN` and NX2 access violation. After the unpowered-system
  guard, deliberate missing-ICD tests for NX2/Eglantine and Eglantine invalid-ROM
  still exited with heap corruption (`0xC0000374`) before bridge construction.
  Both no-ROM tests and NX2 invalid-ROM exited 1. Each process exited without a
  supervisor timeout, but graceful native teardown is **not qualified**. Root
  cause is unresolved; no baseline attribution is claimed.
- Additional buttons/axes, C-stick, process-loss/reconnect, disconnect input
  cleanup, capture-timeout recovery, broker mode, other hosts/drivers and visible
  GPU modes require separate live evidence.
- Pause, exact step/timed tap, debugger/memory access and save states are absent
  capabilities. Paused stability is unqualified. CTR Luma custom-SVC probes and
  Dart JIT/AOT qualification are outside this change.

These cells stop under the plan's qualification stop conditions. They do not
become passing cells because source, unit or build checks passed.

## Review and retained evidence

The original full `ce-code-review` receipt is
`emucap-ce-review-20261104-043105-24882c05/review.json`, status complete, zero
surviving actionable source findings after six fixes. Its freeze predates the
touch/build follow-up, so it does not claim to review those later bytes.

Follow-up review: `emucap-ce-followup-20261104-092813-84d63527/review.json`.
It completed with no actionable findings across eight local lenses and the
configured cross-model peer. Its source-review verdict is ready; it explicitly
does not qualify the listed native/rendering/Switch 2 failure cells. There are
no unapplied source findings. Final package validation remains caller-owned.
The later Ozone investigation changes documentation and build-only evidence.
No push or PR is authorized.

Evidence includes `emucap-final-fast/fast-results.json`, per-lane logs,
`emucap-final-eden-build-tests.log`, current/baseline/fixed repeated-test receipts,
all live calls and PNGs, native build/profile/compiler/OpenSSL provenance,
partial-start diagnostic receipts, and the final package validation manifest.
Private authentication records/runtime homes are not copied into the witness
bundle; allowlisted native logs and redacted identity/exit records are retained.
All results are local, not hosted CI or published release evidence.

## Exact changed paths

At checkpoint `cfc8b74`, the following 100 paths differed from the base. Paths are relative to
`B:/dev/GitHub/emucap`.

```text
.github/workflows/core-validation.yml
.github/workflows/emulator-bridge-validation.yml
AGENT_GUIDE.md
CHANGELOG.md
COMPATIBILITY.md
Cargo.toml
FORK.md
NOTICE
README.md
_tests/emulator-bridges/fast.py
_tests/emulator-bridges/live.py
_tests/emulator-bridges/native_build.py
_tests/emulator-bridges/test_failures.py
_tests/emulator-bridges/test_live.py
_tests/live/emulator-family/.gitignore
_tests/live/emulator-family/README.md
_tests/live/emulator-family/build_fixture.py
_tests/live/emulator-family/ctr.c
_tests/live/emulator-family/qualify.py
_tests/live/emulator-family/switch.c
_tests/live/emulator-family/test_qualify.py
_tests/release/package_core.py
_tests/release/package_core_tests.py
adapters/azahar/.gitignore
adapters/azahar/README.md
adapters/azahar/bridge.py
adapters/azahar/build.ps1
adapters/azahar/build.py
adapters/azahar/build.sh
adapters/azahar/patches/0001-managed-libretro-core.patch
adapters/azahar/test_abi.py
adapters/azahar/test_bridge.py
adapters/azahar/test_build.py
adapters/azahar/tests/build_fixture.py
adapters/azahar/tests/fake_core.c
adapters/azahar/upstream.lock
adapters/eden-family/.gitignore
adapters/eden-family/README.md
adapters/eden-family/build.ps1
adapters/eden-family/build.py
adapters/eden-family/build.sh
adapters/eden-family/native/EmucapBridge.cpp
adapters/eden-family/native/EmucapBridge.h
adapters/eden-family/native/EmucapEdenIntegration.h
adapters/eden-family/patches/eden-nx2.patch
adapters/eden-family/patches/eden.patch
adapters/eden-family/patches/eglantine.patch
adapters/eden-family/profiles/eden-nx2.json
adapters/eden-family/profiles/eden.json
adapters/eden-family/profiles/eglantine.json
adapters/eden-family/tests/bridge_tests.cpp
adapters/eden-family/tests/endpoint_fixture.cpp
adapters/eden-family/tests/run.py
adapters/eden-family/tests/test_build.py
contracts/catalog.json
contracts/exceptions.json
docs/emulator-family-qualification.md
docs/emulator-family-validation.md
docs/plans/2026-11-04-0231-feat-azahar-eden-family-support-plan.md
docs/switch2-ozone-research.md
src/azahar_host.rs
src/azahar_host_tests.rs
src/bin/emucap-azahar.rs
src/bin/emucap-mcp/args.rs
src/bin/emucap-mcp/debug_input.rs
src/bin/emucap-mcp/debug_input_tests.rs
src/bin/emucap-mcp/debug_surface.rs
src/bin/emucap-mcp/launch.rs
src/bin/emucap-mcp/launch/emulator_family.rs
src/bin/emucap-mcp/launch/plan.rs
src/bin/emucap-mcp/launch/run.rs
src/bin/emucap-mcp/launch/system.rs
src/bin/emucap-mcp/launch_tests.rs
src/bin/emucap-mcp/observation_speed_tests.rs
src/bin/emucap-mcp/status.rs
src/bin/emucap-mcp/status/capability_revision.rs
src/bin/emucap-mcp/status/feature_capabilities.rs
src/bin/emucap-mcp/status_tests.rs
src/bin/emucap-mcp/temporal.rs
src/bin/emucap-mcp/temporal/tests.rs
src/content_identity.rs
src/content_identity/exefs.rs
src/content_identity_tests.rs
src/contracts_tests.rs
src/emulator_profile.rs
src/emulator_profile_tests.rs
src/launch/emulator_family.rs
src/launch/emulator_family_tests.rs
src/launch/mod.rs
src/lib.rs
src/live/link.rs
src/live/mod.rs
src/live/progress.rs
src/live/progress_tests.rs
src/live/reconnect_tests.rs
src/live/temporal.rs
src/live/temporal/wire/tests.rs
src/live/tools.rs
src/live/tools/progress_wait_tests.rs
tests/emulator_family_preflight.rs
```

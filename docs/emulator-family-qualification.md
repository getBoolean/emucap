# Experimental emulator-family qualification

This is the evidence boundary for the Azahar, Eden-family and Ryubing development work.
Source preparation, synthetic protocol tests, native builds and live guest
qualification are separate results. No Switch 2 game-compatibility claim is made.
The requested Eglantine source is **Djihads80/Eglantine**, branch `nx2`, revision
`c54bc2289bfffda7fa3cc4c3a8cf522d84a10fd4`; it supersedes the earlier Selevet plan target.

The subsequent [control recovery](emulator-control-recovery.md) records updated
native patch/executable hashes, clean failed-start regression results on all
three Eden forks, three repeated Switch 2 control runs on each maintained fork,
and passing automatic 12 GiB transitions. These current runs explicitly select
Intel Vulkan on this host; at that time AMD surface-capability queries failed even
outside the emulator. A later standalone WSI probe succeeded on both adapters;
AMD guest behavior still needs its own qualification. Earlier evidence below remains historical rather than
proof of the updated binaries.

The [Ryubing integration record](ryubing-qualification.md) covers its separate
Ryujinx-family Switch 1 source build, startup corrections and actual homebrew
control. It does not extend Ryubing to Switch 2.

## Source and operation matrix

| Profile | Source target | Implemented bridge scope | Live status |
| --- | --- | --- | --- |
| Azahar | `9c38437daad90a2f05f55a047d04d4073a476456` | Supervised libretro ABI, combined software capture, persistent digital/analog/touch, native profile/root attestation, running progress waits; no pause | Windows x86-64 software: lawful CTR witness passed within scope below |
| Eden | `5df599128d6828fa0e42968909da848c255d22b1` | Shared SDL producer, input/touch, GPU capture, render-progress wait, managed profile/root binding | Windows x86-64 hidden Vulkan: lawful Switch 1 witness passed |
| Eden-NX2 | `eden-nx2`, `50fa86bbbc403ad565eb44fcc281f16f77c69e15` | Same protocol, source-specific integration; concrete Switch 2 loader/system paths | Windows x86-64 hidden Vulkan: Switch 1 and configured Switch 2 homebrew witnesses passed |
| Eglantine | Djihads80 `nx2`, `c54bc2289bfffda7fa3cc4c3a8cf522d84a10fd4` | Same protocol and explicit source pin; experimental Switch 2 target | Windows x86-64 hidden Vulkan: Switch 1 and configured Switch 2 homebrew witnesses passed |
| Ryubing | `a61a42681119bf15fe8f3297677ae48bda83e70f` | Separate Ryujinx-family producer; shared transport, controller/touch, GPU capture, observed progress, pause/resume | Windows Vulkan/OpenGL and Linux Compose Mesa Vulkan with explicit software-page-table config: Switch 1 witness passed; see exact builds in its record |

Upstream Eglantine calls itself very experimental and publishes game compatibility
claims in its [README](https://github.com/Djihads80/Eglantine). Those are upstream
claims, not emucap measurements or evidence of a particular host/configuration.
Eden-NX2's default `master` is not the audited experimental branch.

At the new Eglantine pin, `src/core/core.cpp` recognizes Switch 2 metadata and
selects a 12 GiB layout; `src/core/file_sys/program_metadata.*` and
`src/core/hle/kernel/k_process.*` carry target identity; and
`src/video_core/renderer_vulkan/vk_texture_cache.cpp` has Switch 2 ASTC branches.
These are concrete implementation paths. Stub service interfaces and guessed
commands also remain in that tree. Their presence does not establish a complete
Switch 2 service/GPU implementation or successful guest execution.

Exact step, timed `tap`/touch pulse, memory/debugger access and save states are not
implemented for these profiles. Absent operations fail through capability admission.
`native_render_present` observes compositor events; `libretro_present` observes
completed software callbacks. Neither proves guest instruction, controller-poll,
or deterministic frame boundaries. Persistent input owners must release input.

## Evidence collected locally

- Rust profile, content identity, launch selection, capability revision, touch
  admission and temporal wait tests exercise the shared production paths.
- Python worker tests load a compiled C fixture, including ABI rejection,
  software buffer ownership, input mapping and lifecycle. Rust subprocess tests
  cover supervision and authenticated transport. They do not run Azahar.
- Eden-family native tests compile shared C++ code and run an authenticated ECFA
  loopback endpoint with synthetic owner hooks, PNG decode, input/touch, wait
  cancellation and detach release. They do not run an emulator.
- Each Eden-family patch applies at its exact source pin. Application alone is
  not proof that the complete emulator compiles or that hook lifetimes are correct.
- Original CTR and Switch 1 fixtures compile with the installed devkitPro
  toolchains. `fixture.json` records exact compiler/source/output identity.

No remote CI execution is claimed. Lower layers do not establish live behavior.
The [live harness](../_tests/live/emulator-family/README.md) writes blocked
evidence and exits nonzero for missing prerequisites.

### Windows Azahar live witness

The real MinGW core completed all 1,502 build steps, loaded through ctypes, and
exported a profile exactly matching its sidecar. Core SHA-256:
`915f475a694a948432ebebc365ac223c3fc484cca0c50e407fe8985097e362ce`.
Patch SHA-256: `c9ed47180aa76f50fad274ca08a927f770767df26d86521de8d56eca6a5cd85a`.
Original CTR fixture SHA-256:
`c2a3c036df994f751917f37482897e1ed5f7e6dbdc13147d502cdc9a4f0ceaa2`.

Managed launch passed actual compiled-profile/effective-root readback. Captured
400×480 software pixels decoded an advancing guest loop counter, A-button and
positive left-stick X consumption and release, and touch at (0,0), (160,120),
(319,239) plus release. Cancelling an active public MCP running wait recovered
control while guest pixels still showed the unrelated A/stick hold. Normal
managed stop verified both worker and supervisor exited. No display server or
hardware renderer was used.

The successful expanded run is `emucap-live-azahar-005` under the local temporary
evidence directory. Earlier cancellation harness attempts incorrectly expected
durable transition records for a read-only progress observation; those failed
runs remain failed evidence. Their exact owned processes were retired with
process-start identity checks and subsequent managed-stop exit verification.
They do not establish a native cancellation defect. Windows process-loss/reconnect,
disconnect input cleanup and capture-timeout recovery remain unqualified, as do
the other stick directions/buttons and C-stick on a real guest. Pause and exact
stepping are unsupported. Linux/macOS live cells remain unqualified.

The expanded run also rejected a mismatched compiled-profile replacement before
disturbing the existing generation. Cancellation returned control in 0.343 seconds
while the guest retained unrelated held input. A synthetic 400×480 callback
measurement on CPython 3.12 fell from a median 139.868 ms to 0.934 ms after raw
buffer copying replaced eager pixel conversion; PNG encoding occurs on capture.
This is callback cost, not an emulator FPS measurement.

Run `emucap-live-azahar-006` repeated the expanded witness using the extracted
Windows Core package from clean source commit `6be8911`, including its packaged
worker resources. It passed the same pixel/input/touch/replacement/stop checks;
active-wait cancellation recovered control in 0.203 seconds. Package startup and
live guest evidence therefore remain separately reproducible.

### Eden-family build boundary

All three maintained pins pass source patch application, matching CMake
generation and strict SDL/glue object compilation against their own generated
headers. The shared producer also compiles and passes synthetic native tests on
Windows and WSL/Linux. Full Windows GNU executables subsequently linked for all
three pins, and each native `--emucap-build-profile` exactly matched its sidecar.
GCC12 warnings in unchanged pinned source were reproduced against the baseline;
the full Eden build uses the supported `ENABLE_WERROR=OFF` option with diagnostics
retained, bounded jobs and a matched same-volume MSYS Perl/make pair. The build
recipe recognizes the upstream `eden-cli.exe` output and stages the selected
compiler's runtime DLLs beside `eden-sdl.exe`, independently of an older GCC on PATH.
It queries the staged executable before publishing the final sidecar.

The installed MinGW-w64 10 headers fail an unmodified Xbyak 7.40.1 probe because
`PROCESSOR_RELATIONSHIP::EfficiencyClass` is absent. A task-local WinLibs GCC 16.2 /
MinGW-w64 14 toolchain passes that same probe. Native retries select that compiler
explicitly; they also disable optional physical libusb input and retain virtual
controller/touch support. Neither the machine toolchain nor global PATH is changed.
The Windows GNU recipe disables httplib's optional async DNS resolver after its
unmodified header independently reproduced a missing `GetAddrInfoExCancel` error;
the fallback header probe passes. This setting does not add a network capability
to the emulator bridge, which connects to numeric loopback addresses.

### Windows Eden-family live witnesses

The original libnx Switch 1 fixture passed with all three source-patched builds
on Windows 11 x86-64, AMD Radeon RX 7900 XT, Vulkan 1.4.359 / AMD driver 2.0.416,
and hidden SDL windows. These are separate fork/build cells:

| Fork | Local evidence directory | Native executable SHA-256 | Cancellation recovery |
| --- | --- | --- | --- |
| Eden | `emucap-live-eden-002` | `161caa24d98c0fe2123595c5fdc36f32b3f095cbb37caf12c5aef4413616a8c8` | 0.094 s |
| Eden-NX2 | `emucap-live-eden-nx2-003` | `2781c3d0fce489cce2f95edd3c881f8892c3a2e68e1c870e17e0b82ab656cb09` | 0.188 s |
| Eglantine | `emucap-live-eglantine-002` | `6e06baa18c86078868dde09fb84552470e5784276e79ffe939655df92ea4e158` | 0.109 s |

Each run decoded the actual guest's pixels and advancing loop counter, A-button
and positive left-X hold/release, touch corners/center/release, and continued held
input after cancelling an admitted running wait. A mismatched-profile replacement
was rejected while preserving the connected generation. Managed stop verified the
owned emulator exited. Switch fixture SHA-256:
`20e32a4d8f69e1619ebd1a6b7812f6d5c6d1dccc762b243c01b954598631de10`.

The native HID sensor clamps the outer 15 pixels. Its capability therefore reports
1280x720 logical dimensions plus inclusive bounds **x=15..1264, y=15..704**.
The bridge and MCP reject coordinates outside that rectangle before mutation;
the witness also proves rejection of (0,0) preserves the held touch. Legacy NDS
and Azahar capabilities without a rectangle retain their full advertised area.
Azahar run `007` passed again with this shared-schema change.

Hidden OpenGL runs for Eden (`003`) and Eden-NX2 (`002`) produced all-black PNGs
and failed the guest-magic assertion. An Eden visible OpenGL attempt (`004`)
failed readiness. These cells are unqualified; their cause is unresolved.
Eglantine OpenGL was not qualified. Initial NX2/Eglantine Vulkan attempts failed
startup, including one observed `VK_ERROR_UNKNOWN`; successful later witnesses
do not erase those attempts or establish their cause.

Partial-start diagnostics are also separate: no-ROM runs exit 1 for both forks,
and invalid-ROM exits 1 for NX2. Eglantine invalid-ROM and deliberately missing
Vulkan-ICD runs for both forks exited with Windows heap-corruption status
`0xC0000374`, before the bridge was constructed. An earlier NX2 failure exited
`0xC0000005`. The SDL patch guards shutdown of an unpowered system, but these
results do **not** qualify clean native failure teardown. Every diagnostic process
exited without a supervisor timeout; this does not establish graceful cleanup.
No baseline attribution or fix for the remaining native crash is claimed.

Other buttons/stick axes, process-loss/reconnect, disconnect input cleanup,
capture-timeout recovery, broker mode, other GPUs/hosts and visible Vulkan remain
unqualified. Native pause is absent, so paused stability and exact stepping do
not receive passing live credit. Switch 1 witnesses cannot qualify Switch 2.

## Live blockers and recovery

The lawful Ounce ExeFS fixture now passes on both Switch 2 forks. See
[the current Ozone/NPDM evidence](switch2-ozone-research.md) for the open-tool
extension, independent beetool parse, exact hashes and live results. The passing
configuration uses a fixed 64 MiB guest heap and preselected native 12 GiB layout.
NX2's default layout transition and automatic heap paths remain failed evidence.
This qualifies the tested emucap primitives, not general Switch 2 game compatibility.
Later managed repeats exited before readiness; a standalone repeat recorded a
Vulkan initialization failure and subsequent native access violation. Stable
repeated launch on this driver remains unqualified; the evidence link above
retains the passing and failed attempts separately.

1. Build and qualify additional hosts/renderers independently using the documented
   dependencies. Keep each executable, compiler runtimes and matched sidecar together.
   The completed Windows builds do not establish Linux/macOS build or live results.
2. Diagnose the failed OpenGL and partial-start native teardown cells before
   claiming support there. Retain failing logs and exit status alongside any retry.
   Additional input axes/buttons require their own guest-visible witnesses.
3. Qualify broader Switch 2 behavior independently. The initial NPDM packaging
   blocker is resolved for the source-built witness; broader services, GPU
   features, default memory transitions and automatic heap accounting are not
   qualified by that witness. A Switch 1 NRO still cannot qualify Switch 2.
4. Qualify cancellation, capture timeout, disconnect and process-loss cleanup on
   actual emulators, and test direct/broker paths, visible/hidden GPU and software
   display-free modes independently. Record unsupported drivers/configurations.

CTR probes requiring Luma custom SVCs are unsupported by this patch. An AOT result
does not qualify JIT, and a screenshot does not establish runtime probe success.
No firmware, keys, commercial media, external publication or 3ds_flutter changes
are part of this work.

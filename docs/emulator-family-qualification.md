# Experimental emulator-family qualification

This is the evidence boundary for the Azahar and Eden-family development work.
Source preparation, synthetic protocol tests, native builds and live guest
qualification are separate results. No Switch 2 game-compatibility claim is made.
The requested Eglantine source is **Djihads80/Eglantine**, branch `nx2`, revision
`c54bc2289bfffda7fa3cc4c3a8cf522d84a10fd4`; it supersedes the earlier Selevet plan target.

## Source and operation matrix

| Profile | Source target | Implemented bridge scope | Live status |
| --- | --- | --- | --- |
| Azahar | `9c38437daad90a2f05f55a047d04d4073a476456` | Supervised libretro ABI, combined software capture, persistent digital/analog/touch, native profile/root attestation, running progress waits; no pause | Windows x86-64 software: lawful CTR witness passed within scope below |
| Eden | `5df599128d6828fa0e42968909da848c255d22b1` | Shared SDL producer, input/touch, GPU capture, render-progress wait, managed profile/root binding | Unqualified pending linked emulator and legal fixture run |
| Eden-NX2 | `eden-nx2`, `50fa86bbbc403ad565eb44fcc281f16f77c69e15` | Same protocol, source-specific integration; concrete Switch 2 loader/system paths | Switch and Switch 2 independently unqualified |
| Eglantine | Djihads80 `nx2`, `c54bc2289bfffda7fa3cc4c3a8cf522d84a10fd4` | Same protocol and explicit source pin; experimental Switch 2 target | Switch and Switch 2 independently unqualified |

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

### Eden-family build boundary

All three maintained pins pass source patch application, matching CMake
generation and strict SDL/glue object compilation against their own generated
headers. The shared producer also compiles and passes synthetic native tests on
Windows and WSL/Linux. These results do not establish a linked emulator.
GCC12 warnings in unchanged pinned source were reproduced against the baseline;
the full Eden build uses the supported `ENABLE_WERROR=OFF` option with diagnostics
retained, bounded jobs and a matched same-volume MSYS Perl/make pair. Full build
results and any live Switch witness remain separate from these object checks.

## Live blockers and recovery

1. Obtain successful source-patched native builds using the documented dependencies.
   Keep the compiled profile and sidecar together; resolve configure/link failures
   before calling an emulator ready. Separate build results by fork and host.
2. Run the original CTR/Switch witnesses on each claimed fork/system/renderer cell.
   Decode guest-visible counters, digital/analog input and touch corners/center,
   prove release and paused stability, retain logs/screenshots and process exit.
3. Supply a lawful Switch 2 homebrew ABI/toolchain and matching target metadata.
   The libnx Switch 1 fixture cannot qualify this cell. Offline loader/shader data
   tests and upstream game claims cannot substitute for a live witness.
4. Qualify cancellation, capture timeout, disconnect and process-loss cleanup on
   actual emulators, and test direct/broker paths, visible/hidden GPU and software
   display-free modes independently. Record unsupported drivers/configurations.

CTR probes requiring Luma custom SVCs are unsupported by this patch. An AOT result
does not qualify JIT, and a screenshot does not establish runtime probe success.
No firmware, keys, commercial media, external publication or 3ds_flutter changes
are part of this work.

# Emulator launch and control recovery

This follow-up starts from `10dc561`, in the existing local checkout. It fixes
failed native teardown and makes the working host GPU selection reproducible.
All three native builds, failed-start regressions and live control checks passed
within the explicit host/device scope below.

## Confirmed causes

The current AMD driver fails `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` with
`VK_ERROR_UNKNOWN` before swapchain creation. A standalone Win32/Vulkan program,
without an emulator, returned the same error for AMD Radeon RX 7900 XT and
success for Intel UHD Graphics 630, for both hidden and visible windows. The
native debugger independently stopped at that exact call in the emulator.
Disabling implicit Vulkan layers did not resolve it. Passing a valid Windows
instance handle was also tested and did not resolve it; that diagnostic edit
was removed. No driver replacement or global graphics setting was performed.
The reduced probe source and captured output are retained as
`C:/Users/Boolean/AppData/Local/Temp/emucap-wsi-probe.cpp` and
`emucap-control-wsi-probe.log` in that same temporary directory.

Selecting host Vulkan device 1 (Intel) in the existing emulator configuration
passed the full NX2 live witness. This is an explicit selection, not a silent
renderer substitution. Device indexes are host-specific. The fixture builder's
new `--vulkan-device` option records the index and generated config hash; the
native log records the actual device and driver. The AMD driver path is not
claimed repaired by selecting another GPU.

Separately, failed startup could corrupt the process heap during thread exit.
The kernel stored an owning `std::optional<KThread>` in emulated TLS. MinGW's
runtime released that TLS allocation before calling the C++ destructor, which
then destroyed a vector in already-freed `0xFEEEFEEE` storage. A minimal ordinary
thread-local vector reproduced it under the same compiler/runtime and GDB's
debug heap. This matches the documented
[MinGW TLS lifetime issue](https://github.com/msys2/MINGW-packages/issues/2519).

The maintained Eden, Eden-NX2 and Eglantine patches now keep TLS trivially
destructible, with stable heap dummy-thread objects owned by the kernel.
The owner registry is mutex-protected and destroyed after kernel worker owners.
`System::~System()` joins CoreTiming before destruction reaches the kernel.
Supplied guest threads retain their original ownership. Dummy objects remain
alive until kernel destruction, when they are freed.

## Reproduction and regression

The new opt-in native regression intentionally selects nonexistent Vulkan
device 999. It requires the actual invalid-device log and a clean native exit 1
under GDB; a crash, hang, unrelated startup error, missing prerequisite or debugger
fault fails the check. It does not grant live guest-control credit.

```powershell
py -3.12 _tests/live/emulator-family/qualify_startup_failure.py --binary C:/build/nx2/eden-sdl.exe --gdb C:/toolchain/bin/gdb.exe --content C:/fixtures/ounce/exefs/main --system switch2 --output C:/evidence/nx2-failed-start
```

Before the fix, this regression failed against NX2 binary SHA-256
`2781c3d0fce489cce2f95edd3c881f8892c3a2e68e1c870e17e0b82ab656cb09`.
Evidence is `C:/Users/Boolean/AppData/Local/Temp/emucap-control-startup-before-nx2/`.
The ordinary minimal TLS probe failed; explicit heap ownership with trivial TLS
passed ten thread exits under the same debugger setup.

## Native builds and live verification

The source revisions remain the pinned maintained profiles. New builds go into
each existing build cache's `fixed-bin/`, leaving prior qualified binaries in
`bin/`. Native profiles bind the changed patch digest. No Rust protocol/schema
change is involved; live verification uses the previously qualified MCP binary.

The explicit-GPU fixture is
`C:/Users/Boolean/AppData/Local/Temp/emucap-control-ounce-intel-fixture/`.
It retains the previously tested unsigned `main` and Ounce `main.npdm`, a fixed
64 MiB heap and the 12 GiB configuration, adding only Vulkan device 1. No
commercial ROM, firmware, key, security bypass, push or PR is part of this work.
The updated handoff archive is
`C:/Users/Boolean/AppData/Local/Temp/emucap-verified-ounce-controlled.zip`, SHA-256
`afe09302647633df1fcfc90b7eb5afa25cce31bd5efeb7fef1868e8d439f2d83`.
It contains the unchanged ExeFS, explicit Intel config, bound manifest and license.

The live control witness checks authenticated native target identity, changing
guest pixels/counter, controller hold/release, touch movement/release, cancellation
preserving unrelated held input, rejected replacement preserving the generation,
and managed shutdown. Exact stepping and pause remain unsupported.

### Completed results

All evidence directories below are under
`C:/Users/Boolean/AppData/Local/Temp/`.

| Profile | Native executable SHA-256 | Patch digest | Live result |
| --- | --- | --- | --- |
| Eden | `e915b48fb6ccf0b2386af7472e93e576bb378e10a5d67c45e85599cb8a0ab263` | `4607e8f68c21b0da885789dcd9127c911ef99a081c514a4a7570dc63242afdf3` | Switch 1 control passed with preselected and default memory layouts |
| Eden-NX2 | `07d2d06ec3a6c478b93d7f86bdb030aa9c2f400a54b7c5951d5771e0f07bb558` | `d5db9705001f00188a69ebcb827e7467066680300f16ad7221e52edda912c44b` | Three independent Switch 2 control runs passed, plus the automatic memory-layout transition |
| Eglantine | `3258d9be817b9cf33e40d30adf98bcc5b02f25d3b7ebd4016ae35ff462677614` | `3ae414300ba26c85dc6e2b7782e01080d27a4e9edbc3c84b8b6fb4898aa37d85` | Three independent Switch 2 control runs passed, plus the automatic memory-layout transition |

The ten passing live runs are `emucap-control-eden-switch1`,
`emucap-control-eden-switch1-default-memory`, `emucap-control-nx2-repeat-1`
through `-3`, `emucap-control-eglantine-repeat-1` through `-3`,
`emucap-control-nx2-default-memory`, and
`emucap-control-eglantine-default-memory`. Each contains its exact binary,
content and config hashes, full status/identity readbacks, pixel captures,
input/release/cancellation checks and managed exit evidence.

All three failed-start regressions passed:
`emucap-control-startup-after-eden`, `emucap-control-startup-after-nx2`,
and `emucap-control-startup-after-eglantine`. The same NX2 check was red before
the ownership fix. `EMUCAP_INFERIOR_EXIT=1` and the absence of debugger faults
establish clean native failure, not merely process disappearance.

The Intel configuration from the source-built fixture has SHA-256
`7eb57272466f7c224fb131a338db91dbd0177df164970e8ac11377d5979c03cd`.
The GPU-only config used to test automatic memory selection has SHA-256
`4d4e6a41e1fd3c667c8188bf0dd0cceb6ff2f40d9f410aaecf31dc448188b9d5`;
the native logs show Ounce detection and automatic selection of the 12 GiB layout.
The guest still requests its fixed 64 MiB heap. The former automatic whole-pool
allocation abort is not qualified by these tests.

Thirteen focused Python tests, four adapter tests, fresh exact patch application
for all three forks, all six fast native/protocol/package lanes, 191 Rust launch
tests, Python compilation and Clippy passed. The initial overly narrow Rust
filter selected zero tests and receives no verification credit; the broader
`launch::` filter ran the 191 tests. Hosted CI was not run.

The scoped simplify pass completed with no changes or findings. The completed
full code review (`20261104-native-control-final`) also retained zero findings:
five local lenses and one independent Claude-provider pass, with no failed
reviewer or unresolved gate. Its receipt is
`C:/Users/Boolean/AppData/Local/Temp/compound-engineering-Boolean/ce-code-review/20261104-native-control-final/review.json`.
The source patches and real failed-start witness encode the lifetime constraint;
this report retains the separate host-driver diagnosis and live proof boundaries.

### Using the control interface

Select the appropriate `fixed-bin/eden-sdl.exe` and the fixture's `emulator.ini`
in `launch_plan`, approve the returned ExeFS graph, launch, then refresh full
`status`. Describe `debug` and use its returned schema/revision to send
`set_input` with port 0, buttons and stick axes. Use `wait_for_running_frames`
to observe compositor progress, and release with `set_input` using empty buttons
and axes. Release held input even when a wait is cancelled. These are persistent
controller operations; exact timed `tap` and deterministic stepping are not
advertised. The touch operation similarly supports explicit press/move/release
within the bounds returned by live status.

GPU indexes and driver qualification are host-specific. This result does not
repair the AMD WSI path, qualify OpenGL, arbitrary retail titles, all services,
all controller styles, every button/axis or every process-loss recovery path.

### Changed paths

- `adapters/eden-family/patches/eden.patch`
- `adapters/eden-family/patches/eden-nx2.patch`
- `adapters/eden-family/patches/eglantine.patch`
- `_tests/live/emulator-family/build_ounce_fixture.py`
- `_tests/live/emulator-family/qualify_startup_failure.py`
- `_tests/live/emulator-family/README.md`
- `docs/emulator-control-recovery.md`
- `docs/emulator-family-qualification.md`
- `docs/switch2-ozone-research.md`

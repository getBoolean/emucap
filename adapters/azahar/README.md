# Experimental Azahar bridge

The Rust `emucap-azahar` supervisor owns a private Python 3.12+ worker that loads
the patched Azahar libretro core. Managed launch registers it as the `3ds` backend,
binds its build/content/generation identity, and isolates user data. Native stdout
is redirected away from the bounded private protocol. A hung or crashed worker
retires the generation; Windows uses a kill-on-close job, Linux uses parent-death
signaling, and the worker also monitors its parent's identity.

This replaces the inherited standalone prototype. The core patch is required:
it exports compiled build identity and the effective user root, rejects storage
fallback, initializes touch state, and exits a fatal libretro run loop. A stock
core or fabricated metadata is rejected. See [qualification](../../docs/emulator-family-qualification.md)
before treating a build as usable.

## Build and select

The pinned source is Azahar `9c38437daad90a2f05f55a047d04d4073a476456`.
Build the Rust release binaries with `cargo build --locked --release --bins`.
Use this directory's build scripts for the core and generated
`emucap-emulator-build.json`, with a real Python interpreter matching the native
core architecture. On Windows upstream uses MinGW; the Rust supervisor may use
MSVC. Native dependencies are required separately. Core packages include the
worker, not Python or the emulator library.

```powershell
py -3.12 adapters/azahar/build.py --source-dir adapters/azahar/work/source --build-dir adapters/azahar/work/cmake --output-dir adapters/azahar/build --jobs 2
```

`--cmake`, `--cc`, and `--cxx` select existing tool executables. Unix hosts use
`python3` or `build.sh`; Windows can also use `build.ps1`. Source edits and dirty
submodules beyond the maintained patch are rejected rather than reset.

Use these MCP arguments for both `launch_plan` and `launch`:

```json
{"system":"3ds","content_path":"/absolute/witness.3dsx","emulator":{"fork":"azahar","binary":"/absolute/emucap-azahar","core":"/absolute/azahar_libretro.so","python":"/absolute/python3.12","renderer":"software"}}
```

Use `.dll` on Windows and `.dylib` on macOS. The sidecar defaults to the core's
directory; `profile` can select it explicitly. Defaults also support
`EMUCAP_AZAHAR_HOST`, `EMUCAP_AZAHAR_CORE`, and `EMUCAP_PYTHON`.
The library and sidecar must remain a matched pair. Do not launch `bridge.py`
directly as a public emucap producer.

## Controls and limits

Software callbacks copy the combined screens into owned storage; capture encodes
and caches PNG on demand without retaining a core-owned pointer.
Absolute touch uses bottom-screen coordinates, 320×240, translated into the
core's composite pointer space. The core's circle pad and C-stick use persistent
axes. `set_input` replaces the complete held controller state; empty buttons and
axes release it. Touch hold/release is separate. Broker disconnect releases
ownership. Read runtime `input_axes` and `touch_capability` for the exact schema.

Continuous execution has one owner. Running progress waits observe this loop;
pause/resume are withheld because no guest CPU freeze barrier is qualified. A completed software callback
is a `libretro_present` event, not proof of an exact guest instruction or input
poll. No exact step, timed `tap`, save-state, memory, or debugger capability is
claimed. No Luma custom SVCs are supplied: a CTR runtime probe depending on them
is unsupported, never a passing result. Screenshot or AOT evidence cannot
qualify Dart JIT.

Software rendering intends to require no display server. That intention must be
qualified on an actual core/guest, independently from fake ABI tests. macOS parent
cleanup and all untested host/render cells remain unqualified.

## Check

```powershell
py -3.12 adapters/azahar/tests/build_fixture.py
py -3.12 -m unittest discover -s adapters/azahar -p 'test_*.py'
```

These tests load a compiled C ABI fixture and exercise lifecycle, malformed ABI,
capture, input, and supervision. They do not execute Azahar. The lawful live
witness and its pixel checks are in [`_tests/live/emulator-family`](../../_tests/live/emulator-family/README.md).

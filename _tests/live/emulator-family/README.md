# Lawful emulator witnesses

`ctr.c` and `switch.c` are original CC0 homebrew. Each renders an EMUC magic,
guest loop counter, observed A-button, stick values, touch coordinates/release,
and its actual target identity as black/white pixel cells. CTR also paints its
bottom screen differently while touched. There are no ROM, firmware, keys or
Nintendo SDK dependencies. Build with an existing devkitPro installation:

```powershell
py -3.12 _tests/live/emulator-family/build_fixture.py --devkitpro B:/tools/devkitPro --system 3ds --output _tests/live/emulator-family/out/ctr
py -3.12 _tests/live/emulator-family/build_fixture.py --devkitpro B:/tools/devkitPro --system switch --output _tests/live/emulator-family/out/switch
```

The builder records source/fixture hashes, exact compiler version, invocation,
system and license in `fixture.json` and `build.json`. The same script accepts
Unix paths. No toolchain is downloaded or installed by it. A successful build
proves packaging only.

Run the opt-in managed-launch witness after building the patched emulator and
the Rust release binaries. Use a real Python 3.12+ with Pillow installed:

```powershell
py -3.12 _tests/live/emulator-family/qualify.py --mcp target/release/emucap-mcp.exe --fork azahar --system 3ds --binary target/release/emucap-azahar.exe --core adapters/azahar/build/azahar_libretro.dll --python C:/absolute/python.exe --content _tests/live/emulator-family/out/ctr/witness.3dsx --renderer software --output _tests/live/emulator-family/evidence/ctr
py -3.12 _tests/live/emulator-family/qualify.py --mcp target/release/emucap-mcp.exe --fork eden --system switch --binary adapters/eden-family/build/eden/bin/eden-sdl.exe --content _tests/live/emulator-family/out/switch/witness.nro --renderer vulkan --output _tests/live/emulator-family/evidence/eden
```

Choose a new output directory per attempt. Failure or missing prerequisites writes
`result.json` and exits nonzero. Evidence includes screenshot pixels, MCP/native
logs, full capability/build/root/content readbacks, guest input observations,
progress terminal results and managed stop. The witness rejects an absent magic,
wrong target identity, stalled guest counter, controller/touch mapping mismatch,
unreleased input, or guest counter changing while paused. It does not claim exact
stepping. The harness also cancels an admitted running wait, checks that unrelated
held input survives, and rejects a mismatched-profile replacement without losing
the live generation. Capture timeout recovery and disconnect input cleanup require
additional live witnesses; synthetic endpoint tests do not replace them.

Switch witnesses require the native HID rectangle `x=15..1264, y=15..704` within
the logical 1280x720 touchscreen. They test those supported corners and center,
then reject an unsupported (0,0) request and verify the held touch did not change.
Azahar retains the complete 320x240 touch area. These bounds are protocol data,
not a coordinate tolerance added to hide native clamping.

Hidden GPU tests still require a working display/driver. On Linux, run under
`xvfb-run -a` with an installed Mesa Vulkan/OpenGL driver. Record the exact driver,
ICD, renderer and display mode separately. Azahar software intends to be display-free;
that requires its own actual core/guest proof.

## Switch 2 boundary

Switch 2 homebrew now has a source-built ExeFS witness. Build the pinned
`alula/libnx-ounce` release library first (without installing over libnx), then:

```powershell
py -3.12 _tests/live/emulator-family/build_ounce_fixture.py --devkitpro B:/tools/devkitPro --libnx-ounce-source C:/source/libnx-ounce --libnx-ounce-library-sha256 'REVIEWED_LIBRARY_SHA256' --switch-tools-source C:/source/switch-tools --cc B:/tools/mingw64/bin/gcc.exe --output C:/fixtures/ounce
py -3.12 _tests/live/emulator-family/qualify.py --mcp target/release/emucap-mcp.exe --fork eden-nx2 --system switch2 --binary C:/build/eden-nx2/eden-sdl.exe --content C:/fixtures/ounce/exefs/main --config C:/fixtures/ounce/emulator.ini --renderer vulkan --approve-indirect-media --output C:/evidence/nx2-ounce
```

Use `--fork eglantine` and its matched binary for the other maintained Ounce
profile. Review `fixture.json`, the two ExeFS members and their hashes before
passing `--approve-indirect-media`. That explicit flag carries the returned
graph-bound approval through a second launch-plan check; the default still blocks
composite media. It does not disable emucap content identity or staging.

Supply the expected archive hash from the reviewed pinned-source library build;
the builder rejects a stale archive or untracked `nx` source files. The hash for
the qualified local GCC 16.1 build is recorded in the current evidence report.

The builder pins libnx-ounce and switch-tools, compiles a dedicated Ounce-only
`npdmtool` variant with 0x180-byte signature/modulus storage, and validates the
generated layout and access-section bounds. This is an emucap extension of the
public tool Ozone invokes, not a claim that unmodified npdmtool supports Ounce.
The unsigned metadata contains no keys. Alula's `beetool` independently parses it
as Ounce; that is format inspection, not cryptographic signature verification.

The fixture uses a fixed 64 MiB heap and the supplied INI selects the native
12 GiB memory layout **before** initialization. NX2's default 4-to-12 GiB
reinitialization crashed on this host; its automatic whole-pool heap request also
aborted. These failures remain unqualified. The two settings are explicit parts
of the passing witness configuration, not general Switch 2 compatibility claims.
See [current Ounce evidence](../../../docs/switch2-ozone-research.md).

### Historical blocker

The original `build_fixture.py` Switch 1 build uses libnx and encodes identity 1. The harness refuses
to count it as a Switch 2 fixture, even under Eden-NX2 or Eglantine. At the initial
checkpoint, no verified Switch 2 homebrew ABI/toolchain was provided. A lawful Switch 2 witness must
encode identity 2, supply its source/toolchain/member hashes and valid target
metadata, and pass the fork's loader/services/shader paths. An internal offline
loader-data test can qualify a source path, not guest execution or game compatibility.
Loose ExeFS must go through reviewed indirect-media admission before launch;
the initial NRO/3DSX harness reported that additional prerequisite as blocked.
No commercial assets or guest-security workaround may substitute for it.

The initial build-only probe and its missing-NPDM result remain historical
evidence. The dedicated `build_ounce_fixture.py` and the live results above
supersede that blocker; `build_fixture.py` retains CTR/Switch 1 behavior.

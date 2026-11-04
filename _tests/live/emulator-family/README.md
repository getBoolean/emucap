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

`switch.c` uses libnx's Switch 1 ABI and encodes identity 1. The harness refuses
to count it as a Switch 2 fixture, even under Eden-NX2 or Eglantine. No verified
Switch 2 homebrew ABI/toolchain is provided here. A lawful Switch 2 witness must
encode identity 2, supply its source/toolchain/member hashes and valid target
metadata, and pass the fork's loader/services/shader paths. An internal offline
loader-data test can qualify a source path, not guest execution or game compatibility.
Loose ExeFS must go through reviewed indirect-media admission before launch;
this simple NRO/3DSX harness currently reports that additional prerequisite as blocked.
No commercial assets or guest-security workaround may substitute for it.

The later [Ozone/libnx-ounce investigation](../../../docs/switch2-ozone-research.md)
built an open Ounce library and ELF/NSO probe. That probe lacks validated Switch 2
NPDM metadata and is not an admissible live fixture. The existing `build_fixture.py`
continues to build only the qualified CTR and Switch 1 fixture formats.

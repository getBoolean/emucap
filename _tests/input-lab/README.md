# Input Lab

Original native homebrew that displays **guest-observed** buttons, both sticks,
triggers and touch. It encodes the same observations in a checksummed pixel
record for independent host comparison. Gyro/motion is excluded.

The large-screen view uses actual input-viewer artwork, raw values, stick plots,
trigger bars and a sample counter. Small handhelds use a
compact control grid. DS/3DS have a separate touch canvas. GC/Wii draw all four
ports simultaneously. Test buttons never exit the program; stop the emulator
through emucap or its normal window controls.

This is an implementation in progress across emucap's full catalog. A native
cross-build, host raster test, live emulator run and physical hardware run are
different evidence. A green host CI job qualifies the encoder/decoder contract
only. It does not boot these artifacts.

Current local evidence: [Input Lab qualification](../../docs/input-lab-qualification.md).
Live controls passed on melonDS DS/DS, mGBA/GBA, Dolphin/GC and Wii digital
input, Azahar/3DS, Ryubing and Eden/Switch, and Eden-NX2 plus
Djihads80 Eglantine/Ounce Switch 2. Eglantine needs explicitly disabled FXAA and
ScaleForce for the tiny pixel record. The report records exact builds/configs,
failed attempts and the remaining gates.

## Build

Python 3.12, Pillow, resvg-py 0.5.0 and a local devkitPro installation are used.
The compiler, commands, source digests, artifact digest and build identity are
written to each output's `fixture.json`. Generate outputs outside the checkout:

```powershell
py -3.12 -m pip install Pillow resvg-py==0.5.0
py -3.12 _tests/input-lab/make_art.py --output C:/temp/input-lab/art
py -3.12 _tests/input-lab/build.py --devkitpro B:/tools/devkitPro --system switch --art C:/temp/input-lab/art --output C:/temp/input-lab/switch
```

Other local builder targets: `3ds`, `nds`, `gba`, `gamecube`, `wii`, `switch2`.
Each output directory must be new, so failed evidence is retained. Switch 2
additionally requires the reviewed pinned libnx-ounce source/archive hash,
switch-tools source and host compiler accepted by the existing Ounce NPDM
builder. See `build.py --help` and the Ounce qualification documents. Its artifact
is an ExeFS directory with `main` and `main.npdm`, not an ordinary Switch NRO.
Keep its explicit emulator memory/GPU configuration and separate live proof.

No SDK/toolchain downloads, firmware, keys or games are acquired by the builder.
Native SDK runtime licenses remain separate from the original CC0 fixture code.
Review those notices before redistributing a linked binary. The output includes
the controller artwork's complete terms and acknowledgement.

## Host contract tests and live qualification

```powershell
py -3.12 -m unittest discover -s _tests/input-lab -v
py -3.12 _tests/input-lab/qualify.py --mcp target/release/emucap-mcp.exe --launch-json C:/temp/input-lab/launch.json --output C:/temp/input-lab/live-001
```

`launch.json` uses ordinary emucap `launch` arguments: `system`, `content_path`,
`emulator` (explicit fork/binary/core/config/profile/renderer where required),
and optional `display`. It is an operator-selected local configuration, not an
automatically downloaded emulator. Composite Ounce media requires explicit
`--approve-indirect-media` after reviewing the original built graph.

The live runner handles the maintained 3DS and Switch emulator families only.
It checks every advertised button individually (hold, sustained hold, release),
positive/negative quarter/half/full magnitudes on each stick axis, axis isolation,
all four touch corners/centre, combined controls and complete release. Each
accepted capture must contain a fresh sequence and the exact built guest ID.
Failed captures and the terminal result stay in the evidence directory.

Expected host-to-native Y mappings are explicit: Azahar libretro Y down maps to
native HID Y up; the existing Eden/Ryubing bridge sends native Y up directly.
The 3DS native stick scale is 156, Switch 32767. Tolerances are bounded, not
inferred from the current observed value. Runtime capabilities still determine
which controls are advertised. An advertised control without guest readback
fails; it is not silently skipped.

GC/Wii each occupy four 320x240 quadrants in a 640x480 framebuffer. Crop the
selected quadrant before decoding with `decode(...,320,240)`; verify its port.
DS has two 256x192 screens; 3DS has 400x240 top and 320x240 bottom. The family
runner decodes the top area of the adapter's existing 400x480 3DS composite.
Other layouts require an explicit decoder mapping, not image auto-detection.

## Coverage and remaining work

| Catalog systems | Native implementation | Remaining qualification |
| --- | --- | --- |
| 3ds | libctru buttons, Circle Pad/C-stick, touch | Physical hardware, full lifecycle/cancellation suite |
| switch | libnx buttons, both sticks, touch | Additional peripheral/device configurations and physical hardware |
| switch2 | Separate pinned libnx-ounce/NPDM build | Exact NX2/Eglantine runtime cells, physical hardware |
| nds | libnds keys/touch, Calico ARM7 packaging | DSi/peripherals, full lifecycle and hardware |
| gba | libgba keypad/staged mode-3 framebuffer | Additional peripherals, full lifecycle and hardware |
| gamecube | libogc four PAD ports, both sticks/triggers | Public analog/trigger injection, analog A/B pressure fields, hardware |
| wii | libogc four WPAD ports, Remote/Classic/Nunchuk buttons/sticks/triggers | Expansion identity/calibration, public analog/trigger injection, IR, hardware |
| gb, gbc | Existing legal-header-dependent pacing recipe only | Native Input Lab port; lawful operator header prerequisite |
| nes, snes, gamegear, md, pce, pcfx, wswan, ngp | No Input Lab port yet | Verify target SDK/assembler/build, implement native inputs and renderer |
| saturn, psx, n64, dc, psp, ps2, xbox | No Input Lab port yet | Verify target SDK/build/runtime prerequisites and controller APIs |
| pc98, msx, msx1, msx2, msx2p | No Input Lab port yet | Verify keyboard/joystick native builds and adapter coverage |
| neogeo_mvs, neogeo_aes, neogeo_cd | No Input Lab port yet | Verify original homebrew packaging, native controls and lawful boot prerequisites |

SMS, WonderSwan Color and NGP Color need their actual machine variant retained
even where emucap normalizes the launch system to a family. This table accounts
for every canonical ID; an unimplemented row is not an unsupported-platform
verdict. It remains required work. No all-platform completion is claimed.

The current observation is a sample plus cumulative pressed/released masks,
not an ordered event log. Guided-case UI, bounded event history/overflow,
per-control capability labels, keyboard/pointer/multitouch, pressure extensions,
reconnect/cancellation terminal assertions and full Compose build-to-live jobs
remain outstanding. Current timing waits observe progress, not exact stepping.

## Credits

The Pro Controller reference is derived from
[shmove/gamepadviewer-procon](https://github.com/shmove/gamepadviewer-procon),
revision `4310b6795f1a57053f955d74f54f042aaa98c535`, based on Open Joystick Display
Project and Anthony Mattera (KernelZechs). The original SVG bytes, hashes and full
terms are retained in `docs/design/assets/procon/`. Raster conversion uses
resvg-py and Pillow; original source code and bitmap glyphs are CC0-1.0.

This product includes software developed by "Open Joystick Display Project and
'Anthony Mattera' (http://www.ojdproject.com/)."

OpenAI Codex assisted the native programs, raster/observation format, build and
qualification scripts, tests and documentation. Generated code is accepted only
with separately recorded checks. See the project CREDITS.md and NOTICE.

The DS/GBA live runner also requires visible title and sample labels. Valid
telemetry alone does not qualify the viewer. GBA renders into EWRAM, then copies
the completed mode-3 framebuffer at VBlank to avoid clearing the visible UI
during scanout. This presentation path has emulator proof; hardware remains
unqualified.

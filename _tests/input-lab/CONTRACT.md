# Input Lab native contract

Gyro and motion are excluded. The existing design remains the visual/product
reference; this document defines the first executable native contract.

Each native program samples its platform APIs, maps digital controls to the
stable bit positions below, retains the original native bitset and raw axes,
and draws its own observation record. It never receives expected observations.
Buttons under test never exit the program. Stop it through the emulator/OS.

Digital bits, in order: A, B, X, Y, L, R, ZL, ZR, minus/select, plus/start,
left-stick click, right-stick click, up, down, left, right, SL, SR, Home, Capture.
Higher bits are reserved for subsequent platform controls. No motion fields are reserved.

The record is 32 little-endian u32 words, rendered least-significant bit first
in a 64-column by 16-row grid of 2x2 monochrome cells. Its origin is (8,H-40)
in the primary native framebuffer, so it fits even a 160x144 screen without
paging. The decoder must know the actual framebuffer layout; 3DS captures use
the top 400x240 portion of the 400x480 combined image. Integer nearest scaling
is accepted. Lossy or interpolated cells fail validation.

| Words | Meaning |
| --- | --- |
| 0 | Magic 0x494c4142 |
| 1 | Version 1 |
| 2 | Target: Switch 1=1, Switch 2=2, 3DS=3, DS=4, GBA=5, GC=6, Wii=7 |
| 3 | Guest sample sequence modulo 2^32 |
| 4..5 | Canonical held bits (low/high) |
| 6..7 | Native held bits (low/high) |
| 8..9 | Native left X/Y, right X/Y, signed 16-bit pairs |
| 10 | Left/right trigger unsigned 16-bit pair |
| 11 | Touch X/Y pair, or 0xffffffff when not held |
| 12 | Validity bits: connected=1, left stick=2, right stick=4, triggers=8, touchscreen=16 |
| 13 | Zero-based port |
| 14..15 | Canonical pressed bits observed since startup |
| 16..17 | Canonical released bits observed since startup |
| 18 | Number of sampled digital-state transitions |
| 19 | Native framebuffer width/height pair |
| 20 | Touchscreen width/height pair, zero if unavailable |
| 21 | Native left stick maximum positive magnitude |
| 22 | Native right stick maximum positive magnitude |
| 23 | Native trigger maximum |
| 24 | Stick Y convention: 1=positive up, 2=positive down |
| 25..28 | First 16 bytes of the SHA256 build identity, as four little-endian words |
| 29..30 | Zero, reserved |
| 31 | Standard CRC32 (IEEE) of words 0..30 serialized little-endian |

Sampling sees only guest samples; accumulated masks do not prove an ordered
event history or identify multiple presses. A screenshot proves a particular
sample, not exact frame stepping. A case requires a fresh sequence, complete
held-state/axis/trigger/touch comparison, then a separate neutral release.
The host owns expected mappings and tolerances. Unsupported controls/ports are
reported separately and cannot count as passes.

Implementation order: shared C renderer and independent Python oracle; Switch
and 3DS; DS/GBA; GC/Wii; original Ounce packaging; live fork cells; remaining
catalog toolchain ports. All ports depend on the shared record, asset pipeline
and renderer, so initial writes run serially in this already-dirty checkout.
The web preview and attribution files are offered task artifacts and stay
uncommitted with the rest of this change. No publication is authorized.

Verification: compile the actual common C renderer on the host and decode its
160x144 and scaled output; reject corrupt records and mutated expected controls;
cross-build with warnings as errors; retain per-artifact source hashes/compiler
commands; independently launch original artifacts and test each supported input.
Host tests, cross-builds and actual guest qualification are distinct results.
No all-platform acceptance until every catalog target has a built native port
and all required runtime/device cells have evidence or an explicit blocker.

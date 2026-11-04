# Ozone and the lawful Switch 2 witness

## Current result: Ounce homebrew runs in both maintained forks

The follow-up user request produced `main.npdm` and a complete source-built ExeFS
witness. Eden-NX2 and Djihads80 Eglantine both passed the live Switch 2 witness
on Windows x86-64 / AMD RX 7900 XT / hidden Vulkan with the explicit configuration
below. The earlier missing-metadata findings remain historical evidence.

Ozone's `stratosphere/ro/system_module.mk` invokes the open-source
[switchbrew npdmtool](https://github.com/switchbrew/switch-tools). Its public pin
still has fixed NX sizing. `ounce_npdm.py` therefore builds an explicitly named,
dedicated Ounce-only variant: signature and modulus each grow from 0x100 to
0x180 bytes, and its compile-layout check grows from 0x240 to 0x340. Existing
`sizeof`-based section offsets and signed-data length calculations follow those
sizes. This extension is ours; no public standalone Ounce generator was found.

[Alula's beetool](https://github.com/alula/beetool), revision
`965a13a6b6d0efa9123c4c03dd3a8e80e346717c`, was built independently from source.
Its NPDM parser reports `Platform: Ounce`, the expected application title ID
and stack. Its ACID subdescriptor parser has an offset-base bug: `npdm_get_acid`
returns the magic pointer, but FAC/KAC/SAC readers add offsets relative to the
whole signature/key block. In particular its JSON filesystem permissions are
invalid and are not independent validation. Raw FAC and FAH reads from their
proper section bases both contain the requested `0xffffffffffffffff`; the
generator validates all subdescriptor bounds and the emulators load the result.
Its Ounce signature verification also remains unimplemented;
our generated signature/key slots are deliberately zero for
unsigned homebrew. No signature-validity or console-boot claim is made.

The checked-in tools are `_tests/live/emulator-family/build_ounce_fixture.py`,
`ounce_npdm.py`, and `ounce-witness.npdm.json`. The generated bundle is
`C:/Users/Boolean/AppData/Local/Temp/emucap-verified-ounce-fixture-002/`:

- `exefs/main`: `9a343fafb421247b310e0491ca5935471896f0437d708d9be7a4ac5273f04167`.
- `exefs/main.npdm`: `594482f2415d81643ff3e64bdd446aa0b9ef33408bd9700945fa686211e39ded`.
- ACID starts at 0x80; its magic is at block+0x300; ACID size is 936 bytes.
  ACI0 starts at 1072 and is 152 bytes. Application ID is `040000000001e001`.
- `fixture.json` binds source, library, descriptor, compiler command, members and
  configuration hashes; `LIBOUNCE-LICENSE.md` retains the linked library notice.

| Fork | Local result directory | Outcome |
| --- | --- | --- |
| Eden-NX2 `50fa86bbbc403ad565eb44fcc281f16f77c69e15` | `emucap-live-eden-nx2-switch2-005` | Passed; cancellation recovered control in 0.125 s |
| Djihads80 Eglantine `c54bc2289bfffda7fa3cc4c3a8cf522d84a10fd4` | `emucap-live-eglantine-switch2-003` | Passed; cancellation recovered control in 0.109 s |

Both runs use MCP SHA-256
`83e25540e2a582b137336f2a03471e3adfc9d83998b90e567472e979ae8bf809`
from clean source `cfc8b74`. Native fork binaries match the existing qualification
matrix. No native source or bridge identity was altered to force a Switch 2 result.

Each run verified authenticated native `switch2` readback, staged two-member
ExeFS identity, guest target-2 pixels and advancing counter, A/positive left-X
hold and release, touch corners/center/release, rejection of unsupported touch
coordinates preserving the hold, cancellation preserving unrelated input,
mismatched-profile replacement preserving the generation, and managed process exit.

### Configuration limits and retained failures

The fixture requests a fixed **64 MiB heap**, sufficient for its framebuffers and
runtime. Its generated `emulator.ini` sets `[Core] memory_layout_mode=4` (12 GiB)
before native system initialization. These are part of the passing configuration.

NX2 attempts `001` and `002` exited before hello. A debugger confirmed native
heap corruption (`0xC0000374`) after detecting Ounce and switching layouts.
Attempt `003` used the wrong INI section and is also failed evidence. Correctly
preselecting the layout (`004`) reached native Switch 2 readiness but the guest's
automatic whole-pool heap allocation aborted; native progress remained zero and
the harness failed. A fixed, ordinary libnx heap request produced passing `005`.
This does not qualify the default reinitialization or automatic heap-accounting paths.

Eglantine `001` passed the guest checks but failed harness deletion of read-only
staged files; it remains failed. The cleanup regression is fixed and tested.
Eglantine `002` passed the earlier probe; `003` repeated the complete checked-in
fixture/configuration. A Switch 1 NX2 control also passed during diagnosis.

All evidence directories above are under the local temporary directory. The
probe/compiler logs and debugger stack are retained under `emucap-plan-research/`.
These results qualify basic emucap controls for this homebrew configuration;
they do not qualify Switch 2 games, every service, Ampere shaders, other inputs,
OpenGL, other hosts, exact stepping, pause, or the listed native failure paths.

### Follow-up changed paths and local validation

The follow-up changes exactly these paths:

- `_tests/live/emulator-family/ounce_npdm.py`
- `_tests/live/emulator-family/build_ounce_fixture.py`
- `_tests/live/emulator-family/ounce-witness.npdm.json`
- `_tests/live/emulator-family/test_ounce.py`
- `_tests/live/emulator-family/switch.c`
- `_tests/live/emulator-family/qualify.py`
- `_tests/live/emulator-family/test_qualify.py`
- `_tests/live/emulator-family/README.md`
- `docs/switch2-ozone-research.md`
- `docs/emulator-family-qualification.md`
- `docs/emulator-family-validation.md`

All 13 focused Python tests, Python compilation, all six fast-check lanes and
the Switch 1 fixture compile/package regression passed. A broad parallel Rust
test attempt failed one recording test with Windows socket error 10055
(1694 passed, 1 failed, 4 ignored); that failed attempt is retained separately.
No pre-existing-failure attribution is made. The serial retry
(`cargo test --locked --release --all-targets -- --test-threads=1`) passed all
1,956 tests with four existing ignored tests. Logs are
`emucap-ounce-all-targets.log` (failed parallel attempt) and
`emucap-ounce-all-targets-serial.log` (passing retry), under the local temporary
directory. `cargo clippy --locked --all-targets -- -D warnings` also passed.
The completed review's archive-provenance finding was fixed: the builder now
requires an expected library hash from the reviewed source build and rejects
untracked `nx` files. The qualified library hash is
`c7a13c770a79c0381ed2a2fc351aa07ad8cc2738e515c17029d61962098f9887`.
Two focused regressions cover stale archive bytes and untracked headers.
A fresh guarded build (`emucap-verified-ounce-fixture-003`) produced identical
`main` and `main.npdm` hashes to the live-tested fixture. Config-file hashing was
also added to future live result records.
The completed review receipt is
`C:/Users/Boolean/AppData/Local/Temp/compound-engineering-Boolean/ce-code-review/20261104-ounce-final/review.json`
(run `20261104-ounce-final`): six local review lenses, independent Claude review
and validator, with no P0–P2 findings. Its one P3 archive-binding finding (#2)
was applied inline and verified by the two new tests and identical guarded build;
no review finding remains unresolved.
No hosted CI is claimed.

Later repeat attempts remain separate evidence: NX2 `006` was blocked by a
mistyped MCP executable path; NX2 `007` and Eglantine `004` exited before ready.
A standalone NX2 diagnostic with the same fixture/configuration recorded Vulkan
`VK_ERROR_UNKNOWN` / failed GPU initialization and subsequent native access
violation (`0xC0000005`). It is retained in
`emucap-ounce-retry-diagnostic-ftcm3hcb/log/eden_log.txt`. That explains this
diagnostic's failure, not a proven cause for every failed managed retry. The
earlier two passing cells are actual live evidence; stable repeated launch on
this driver remains unqualified.

The handoff archive is
`C:/Users/Boolean/AppData/Local/Temp/emucap-verified-ounce-homebrew-v2.zip`, SHA-256
`e7c210e275a223080367f40713ea528a48e863a217b88bd3185888870fe4461e`.
It includes the two-member ExeFS, configuration, manifest, library license and
independent parser output with a `HANDOFF.txt` warning about its descriptor bug.
Source/toolchain files remain in the pinned checkout
and the build evidence directory.

## Initial investigation (superseded blocker)

The user supplied [alula/Ozone](https://github.com/alula/Ozone) during final
emucap validation. This investigation narrows the Switch 2 blocker: an open
userland library can be built, but a validated target-specific bootable fixture
has not been produced. No firmware, keys, commercial code or console exploit was
obtained or run. Ozone is research input, not an emucap backend.

## Inspected sources

| Source | Exact revision | Relevant evidence |
| --- | --- | --- |
| [Ozone](https://github.com/alula/Ozone/tree/5e3c83a58883187f55ed44474f4ffd90127fe3bd) | `5e3c83a58883187f55ed44474f4ffd90127fe3bd` | README points to libnx-ounce; `libraries/config/common.mk` selects `ounce-bee-001`, Cortex-A78C and `libounce`; `stratosphere/ro/ro.Ounce.json` supplies `platform: ounce` |
| [libnx-ounce](https://github.com/alula/libnx-ounce/tree/a04b88b3d3ed059963200d0a3d460754b2fe294e) | `a04b88b3d3ed059963200d0a3d460754b2fe294e` | `nx/Makefile` defines `__SWITCH2__`, ARMv8.2/PAuth and a separate `libounce` install; SVC bindings include `svcSetGpuMemoryAttribute` |
| [switch-tools](https://github.com/switchbrew/switch-tools/tree/22756068dd0ed6ff9734c59cb4f99ebd3f62555b) | `22756068dd0ed6ff9734c59cb4f99ebd3f62555b` | `src/npdmtool.c` uses fixed signature/modulus storage and does not consume a `platform` field |
| [Switchbrew NPDM format](https://switchbrew.org/w/index.php?title=NPDM&oldid=15417) | Wiki revision 15417 | Ounce uses two 0x180-byte signature/key fields, placing the ACID magic at block+0x300 rather than NX's +0x200 |

Ozone's README describes a partial experimental port, not full custom firmware.
Its Atmosphere component work and library port do not establish emulator guest
compatibility. The linked Switchbrew format research is useful independently of
whether an emulator implements the entire platform.

## Local build and packaging probes

The pinned `libnx-ounce` release library built successfully with the installed
devkitA64 GCC 16.1.0. No `make install` was run and the installed libnx was left
unchanged. On this Windows host the build used MSYS2 bash/make and four jobs:

```sh
export DEVKITPRO=/b/tools/devkitPro
export PATH="$DEVKITPRO/devkitA64/bin:$DEVKITPRO/tools/bin:/usr/bin:$PATH"
make -C /absolute/libnx-ounce/nx lib/libnx.a -j4
```

A temporary copy of the original CC0 pixel witness linked against that library
with its Cortex-A78C/ARMv8.2/PAuth flags and packed to NSO using `elf2nso`. It
encodes target identity 2, but is explicitly **not a bootable or qualified
Switch 2 fixture**. The library's license is retained in its source checkout.
Build-only hashes:

- `libnx.a`: `c7a13c770a79c0381ed2a2fc351aa07ad8cc2738e515c17029d61962098f9887`.
- Witness source: `86a8bb8fd97e1c770758cf348efd001a6b9d10ba41cbf7643158e714aa27e777`.
- ELF: `24515a78e0a34ea0bab50868c5f57195834c7a8598c61674bca9900a3e5902c9`.
- NSO: `f0223816e0a722d741060456aa5386e0e5824283687df05884acedf9887f4eaa`.

Running the installed `npdmtool` on Ozone's `ro.Ounce.json` returned exit 0 but
emitted the NX layout: ACID magic at +0x200, not +0x300. This is a failed
target-format probe, not successful Switch 2 packaging. The inspected upstream
switch-tools source also lacks that platform selection. Ozone's system-module
descriptor is a format probe only; it is not the application's metadata.

The pinned Eglantine/NX2 NRO loaders call `ProgramMetadata::GetDefault()` and
therefore identify NROs as Switch 1. Their ExeFS metadata parser recognizes the
larger Ounce ACID layout. Passing `system: switch2`, renaming an NRO or changing
its pixel identity cannot supply the missing loader-visible target metadata.

## Remaining gate

A complete Switch 2 witness needs a source-defined application NPDM using the
documented Ounce layout, matching the NSO's target and permission requirements,
and independent validation of every header/offset/member. An appropriate packer
or a separately tested homebrew metadata writer is still needed. No commercial
signature/key material is required or sought for this emulator-only fixture.

Then run the reviewed loose-ExeFS admission flow, require native
`KProcess::IsSwitch2()` readback, and decode target-2 guest pixels, progress,
controller/touch input and release. Only that run can qualify the basic emucap
Switch 2 cell; it would not prove all services, GPU features or game compatibility.
The current live harness intentionally blocks unreviewed composite media.

Evidence is under `C:/Users/Boolean/AppData/Local/Temp/emucap-plan-research/`:
`libnx-ounce-build.log`, `ounce-witness-probe/{switch2.c,witness.elf,main,probe.json}`,
`ounce-witness-probe.log`, and `ozone-ro-probe.{npdm,json}`. The complete local
compile command and its source/library/output hashes are in `probe.json`.
No live Switch 2 execution or Ozone component execution was performed.

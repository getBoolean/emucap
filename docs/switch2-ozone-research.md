# Ozone and the lawful Switch 2 witness

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

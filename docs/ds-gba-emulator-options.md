# PC DS/GBA emulator choices

Checked 2026-11-04. Desktop applications are installed separately from the new
opt-in software-core integration. See [setup and capabilities](../adapters/libretro/README.md)
and [live evidence](input-lab-qualification.md).

## What this emucap checkout currently selects

`src/bin/emucap-mcp/launch/system.rs` routes Nintendo DS to `desmume_nds`,
GBA to `mesen2`, and GameCube/Wii to `dolphin`. The README lists the same choices.
These are emucap's existing supported integrations, not a ranking of standalone
desktop emulators. An explicit `emulator` selection now routes DS/GBA to the registered
`software_libretro` adapter using melonDS DS or mGBA, respectively.

For immediate emucap automation, keep those existing backends. In particular,
Mesen2's GBA launcher requires a lawful local GBA BIOS; its adapter README explains
the `EMUCAP_GBA_BIOS` provisioning path. No BIOS was acquired in this research.

## Modern desktop candidates

| Target | Candidate | Verified public surface | Integration implications |
| --- | --- | --- | --- |
| DS/DSi | [melonDS](https://github.com/melonDS-emu/melonDS), inspected release tag 1.1 | Windows builds; source has `NDS::SetKeyMask`, `TouchScreen`, `ReleaseScreen`, `RunFrame`; Qt emulation thread uses those APIs | Good candidate for an owned source-side bridge. The stock desktop input/hotkey path is not an authenticated emucap RPC service. New backend selection, capability/schema registration, lifecycle/capture ownership and original-guest qualification are required. |
| GBA/GB/GBC | [mGBA](https://mgba.io/downloads.html), official downloads list 0.10.5 | Windows portable builds; documented Lua `setKeys`, `screenshot`, instruction `step`, and frame/key-read callbacks | Useful hooks for a Lua or native bridge. The docs describe APIs, not emucap compatibility or proven frame determinism. Launch/script transport, input lifetime, capture semantics and supported-build identity still need qualification. |

For a new PC integration I would evaluate **melonDS for DS** and **mGBA for GBA**,
while retaining DeSmuME/Mesen2 as selectable existing backends. The software-core path has passed the original Input Lab Windows qualification;
the stock Qt applications have only installation/version checks. A single new adapter should not silently replace emucap's
current defaults.

melonDS distinguishes direct boot from firmware boot; its README says firmware
boot needs a lawful original DS/DS Lite BIOS/firmware dump. Do not infer DSi boot
prerequisites or broad compatibility from DS direct boot or the presence of
FreeBIOS source. mGBA's scripting documentation notes that most API documentation
was generated from 0.10.2, so exact 0.10.5 behavior still requires a live check.

## Primary sources

- [emucap backend mapping](../src/bin/emucap-mcp/launch/system.rs)
- [Mesen2 GBA requirements](../adapters/mesen2/README.md)
- [melonDS official project and firmware-boot requirements](https://github.com/melonDS-emu/melonDS)
- [melonDS official download page](https://melonds.kuribo64.net/downloadlist.php)
  (search result accessible; direct fetch returned HTTP 403 during this check)
- [melonDS 1.1 native input/frame API](https://github.com/melonDS-emu/melonDS/blob/1.1/src/NDS.h)
- [melonDS 1.1 frontend owner loop](https://github.com/melonDS-emu/melonDS/blob/1.1/src/frontend/qt_sdl/EmuThread.cpp)
- [mGBA official downloads](https://mgba.io/downloads.html)
- [mGBA scripting API and documentation-version caveat](https://mgba.io/docs/scripting.html)

Official GitHub release API responses were subsequently retrieved through Python.
Portable installations are `B:/tools/emucap/melonDS-1.1/melonDS.exe` and
`B:/tools/emucap/mGBA-0.10.5/mGBA-0.10.5-win64/mGBA.exe`. Both version/help
checks passed. melonDS's archive SHA256 matched the published asset digest;
mGBA's release asset did not publish a digest, so its recorded SHA256 is a local
identity check, not an upstream checksum match. Installation receipts are under
`C:/Users/Boolean/AppData/Local/Temp/emucap-input-lab/setup/`.

mGBA 0.10.5 has GUI scripting but no `--script` startup option. Its scripting API
alone therefore does not provide unattended emucap launch. melonDS's stock Qt
frontend similarly has no emucap RPC endpoint. The automation builds are
separately pinned software libretro cores, not desktop key injection. No
commercial ROM, firmware or keys were sought.

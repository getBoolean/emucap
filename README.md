# emucap

**Let AI agents see, play, and debug games in emulators.**

[한국어](README.ko.md) · [Releases](https://github.com/mcpads/emucap/releases) · [Agent guide](AGENT_GUIDE.md)

[Credits and AI usage](CREDITS.md) · [Third-party notices](NOTICE)

emucap connects MCP-compatible agents such as Claude Code and Codex to retro-game
emulators. Ask your agent to play through a scene, reproduce a bug, or investigate
what the game is doing. It can inspect the screen, press buttons, advance frames,
and examine memory through one interface across supported emulators.

## What this fork adds

This fork adds storage-backed DS homebrew, experimental Nintendo emulator
control, and guest-observed input testing.

- **Storage-backed DS homebrew:** attach a writable CompactFlash image when
  launching DeSmuME, so applications can read assets and write files.
- **Pico Loader compatibility:** fixes card detection and interrupt handling
  that could prevent startup or stall filesystem-heavy tasks such as recursive
  searches.
- **Native Windows and Linux packages:** matching emucap and DeSmuME downloads,
  with checksums and source archives for the Pico release.
- **More Nintendo emulator choices:** managed launch, stop, screenshots and
  persistent input for [Azahar](adapters/azahar/README.md) (3DS),
  [Eden, Eden-NX2 and Eglantine](adapters/eden-family/README.md), and
  [Ryubing](adapters/ryujinx-family/README.md) (Switch). Shared family bridges
  support compatible forks through explicit source patches and build profiles.
- **Alternative DS/GBA cores:** opt into
  [melonDS DS or mGBA](adapters/libretro/README.md) through the supervised
  software-core bridge; existing DeSmuME and Mesen2 defaults remain available.
- **Homebrew input verification:** [Input Lab](_tests/input-lab/README.md)
  displays controller and touch state and verifies it from captured guest
  pixels across Nintendo platforms. Dolphin capture also handles CPU-written
  GameCube/Wii framebuffers.

For the published Pico builds, download both the core and DeSmuME package from the
[Pico release](https://github.com/getBoolean/emucap/releases/tag/1.1.0-pico.4).
The newer emulator integrations require matched source builds and remain
experimental. Eden-NX2 and Eglantine have passed Switch 2 homebrew tests;
this does not establish broad Switch 2 compatibility. Controls and touch vary
by adapter; observed progress is not exact stepping, and Ryubing pause does not
promise frozen execution. See [qualification evidence](docs/emulator-family-qualification.md),
[Ryubing results](docs/ryubing-qualification.md), and the
[fork setup notes](FORK.md) for supported configurations and limits.

## What you can do

- **Play and observe:** capture screenshots, press or hold buttons, move the mouse,
  and adjust execution speed where supported.
- **Reproduce a problem:** save a checkpoint, replay inputs, and compare results.
- **Investigate the game:** read memory and registers, set breakpoints, and step
  through instructions.
- **Keep experiment records:** optionally record runs, findings, and comparisons
  with the separate Tracking MCP.

For example, give your agent a game path and ask:

> “Open this game and pause it before we start.”
>
> “Save a checkpoint, hold right for 60 frames, and show me the screen.”
>
> “Find what writes to this memory address when the player takes damage.”

Available operations depend on the emulator and system. The connected runtime
reports them through `status`, so the agent can choose the supported operations.

## Get started

Give your agent this repository and the game you want to use:

> “Install emucap using AGENT_GUIDE.md, register its MCP servers, and prepare the
> adapter for this game.”

The agent installs the core, prepares the selected emulator adapter, and checks
that it can connect. You provide the game and any required BIOS or firmware.

Core packages are available for **Windows x86-64, Linux x86-64, and macOS Apple
Silicon** on [GitHub Releases](https://github.com/mcpads/emucap/releases).
Source builds also support Intel macOS. Emulator adapters are prepared separately;
their build requirements and features vary by host OS.

For manual installation, see the [installation steps](AGENT_GUIDE.md#1-choose-the-core-installation).
The core exposes two MCP servers: **Control** drives the emulator, while optional
**Tracking** stores experiment records. The agent combines them as needed.

## Systems

| Emulator | Systems |
| --- | --- |
| Mesen2 | NES, SNES, Master System, Game Gear, Game Boy / Color, GBA |
| Mednafen | PlayStation, Saturn, PC Engine, PC-FX, Mega Drive / Genesis, WonderSwan / Color, Neo Geo Pocket / Color |
| Flycast | Dreamcast |
| DeSmuME | Nintendo DS |
| melonDS DS / mGBA cores (opt-in, experimental) | Nintendo DS / Game Boy Advance |
| PPSSPP | PSP |
| PCSX2 | PlayStation 2 |
| Dolphin | GameCube, Wii |
| MAME / NP2kai | PC-98 |
| MAME | Neo Geo MVS / AES / CD |
| Mupen64Plus | Nintendo 64 |
| openMSX | MSX1 / MSX2 / MSX2+ |
| xemu | Original Xbox |
| Azahar libretro (experimental) | Nintendo 3DS |
| Eden family (experimental) | Switch; Switch 2 targets in Eden-NX2 and Eglantine |
| Ryubing (experimental) | Switch |

See the [adapter guide](AGENT_GUIDE.md#per-emulator-adapters-the-agent-installs-when-needed)
for setup and each profile’s supported scope. emucap maintains source patches where
native emulator changes are needed for control and observation.

The Azahar, Eden-family, Ryubing and opt-in melonDS DS/mGBA integrations require
matched source builds. See the [software-core adapter](adapters/libretro/README.md) for
DS/GBA selection, setup and qualified capabilities.
Their registration and protocol tests do not establish guest compatibility.
See the [qualification record](docs/emulator-family-qualification.md) for exact pins,
build results, live blockers, and unsupported operations. Eglantine uses
[Djihads80/Eglantine](https://github.com/Djihads80/Eglantine), branch `nx2`.

## Project status

**A stable 1.x release is available.** [COMPATIBILITY.md](COMPATIBILITY.md) defines
the 1.x compatibility commitments; [CHANGELOG.md](CHANGELOG.md) records changes.

The core and otherwise unmarked source are **GPL-2.0-or-later**. Emulator patches
follow their upstream license boundaries. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

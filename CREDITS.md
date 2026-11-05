# Credits and AI usage

This is a provenance and credit record, not an endorsement by the projects or
people named here. It supplements [NOTICE](NOTICE) and [LICENSE](LICENSE);
upstream source files, dependency notices and license grants remain authoritative.
The entries below document this fork's emulator integration work. They do not
claim a complete attribution audit of every historical contribution or dependency.

## Software and tools referenced or used

| Project and contributors | Actual role in this work |
| --- | --- |
| [emucap](https://github.com/mcpads/emucap), mcpads and contributors | Base Rust/MCP project extended by this fork. Existing adapters, tracking, release workflows and notices are retained. Project default: GPL-2.0-or-later. |
| [Azahar](https://github.com/azahar-emu/azahar), Azahar and Citra contributors | Source patched and built for supervised libretro loading, input/touch and combined-screen capture. A lawful CTR witness was exercised; this does not qualify Luma custom SVCs or Dart runtime behavior. See the [qualification record](docs/emulator-family-qualification.md). |
| [Eden](https://git.eden-emu.dev/eden-emu/eden), Eden contributors and emulator lineage credited by its source | Source patched, compiled and used for actual Switch 1 homebrew control. Native integration is GPL-3.0-or-later; bundled components retain their notices. |
| [Eden-NX2](https://git.eden-emu.dev/Takoroka/eden-nx2), Takoroka and contributors | Experimental `eden-nx2` branch inspected, patched, built and exercised with separate Switch 1 and Ounce homebrew fixtures. Switch 2 claims are limited to the recorded fixture evidence. |
| [Eglantine](https://github.com/Djihads80/Eglantine), Djihads80 and contributors | Maintained `nx2` source target, patched and built for the shared Eden-family bridge; actual Ounce homebrew control was qualified. Earlier [Selevet Eglantine](https://github.com/sylvieistaken/selevet-eglantine) research was superseded and is not the maintained build target. |
| [Ryubing](https://git.ryujinx.app/projects/Ryubing.git), Ryujinx Team and Contributors | MIT-licensed upstream source inspected, patched and built for the Ryujinx-family Switch 1 frontend. Actual controller/touch/capture and lifecycle results are in the [Ryubing record](docs/ryubing-qualification.md). emucap's shared native bridge and C ABI carry their own GPL-3.0-or-later notices. |
| [libretro](https://www.libretro.com/), libretro contributors | ABI used by the Azahar supervisor, worker and synthetic lifecycle fixtures. ABI conformance and actual guest qualification are separate evidence. |
| [libctru](https://github.com/devkitPro/libctru) and [libnx](https://github.com/switchbrew/libnx), their authors and contributors | Runtime libraries and APIs used to compile the original CTR and Switch 1 pixel/input witnesses with devkitPro tools. Their license notices apply to linked fixture libraries. |
| [libnx-ounce](https://github.com/alula/libnx-ounce), Alula and libnx Authors | Pinned source-built Ounce runtime linked into the Switch 2 witness. Its ISC notice is retained in generated fixture bundles. Exact source/archive hashes are in the fixture manifest and [Ounce record](docs/switch2-ozone-research.md). |
| [switch-tools](https://github.com/switchbrew/switch-tools), switchbrew contributors and libnx Authors credited in its ISC notice | `nacptool` and `elf2nro` package standard homebrew metadata. Pinned `npdmtool` source was compiled with this project's explicit Ounce sizing extension to create unsigned `main.npdm`. The extension is local work, not an upstream Ounce-support claim. cJSON's separate notice remains applicable. |
| [beetool](https://github.com/alula/beetool), Alula's hactool-derived fork; SciresM and contributors credited by its ISC notice | Independently source-built and used to parse Ounce NPDM fields. Its ACID-offset and signature-verification limitations prevent treating that parse as full permissions or signature validation. |
| [nlohmann/json](https://github.com/nlohmann/json), Niels Lohmann and contributors | MIT-licensed JSON parser used by the native transport. Ryubing builds verify the exact 3.12.0 single-header SHA-256 and include its bytes in the build identity. |
| [SDL](https://libsdl.org/), SDL contributors; [Vulkan](https://www.vulkan.org/), Khronos and implementers; [OpenGL](https://www.opengl.org/), Khronos and implementers | Native emulator windowing, graphics presentation and capture paths inspected and exercised. Specific driver/build results do not establish compatibility with every driver. |
| [Rust](https://www.rust-lang.org/) and Cargo; [Python](https://www.python.org/); [Pillow](https://python-pillow.org/) | Rust 1.94.1 compiled and checked the MCP/launch code. Python 3.12 ran build, ABI and live harnesses. Pillow 11.3.0 decoded actual guest witness PNGs. Rust dependency versions remain in [Cargo.lock](Cargo.lock). |
| [devkitPro](https://devkitpro.org/), [GCC](https://gcc.gnu.org/), [MinGW-w64](https://www.mingw-w64.org/), [MSYS2](https://www.msys2.org/), [CMake](https://cmake.org/) and [Ninja](https://ninja-build.org/) | Compiled the lawful homebrew and native emulator/bridge code. Windows qualification used GCC 12/16; the Linux native build used GCC 13.3.0. Recipes and logs retain exact commands and available versions. Tool/runtime licenses remain separate from fixture source licensing. |
| [.NET](https://github.com/dotnet), Microsoft and contributors | SDK 10.0.403/MSBuild published Windows and Linux Ryubing frontends; runtime 10.0.14 was observed. Frontend publication is distinct from actual guest qualification. `dotnet-stack` 10.0.750501 was used for local managed diagnostics. The complete frontend depends on its upstream managed/native packages. |
| [GDB](https://www.sourceware.org/gdb/), GNU contributors | Diagnosed native startup/teardown faults and checked clean failure exits in the Eden-family work. |
| [Git](https://git-scm.com/), Git contributors; [Docker](https://www.docker.com/) and [Docker Official Images](https://github.com/docker-library/official-images) | Git pins source revisions and preserves the local change history. Docker runs separate Linux validation; container/synthetic results are recorded separately from Windows emulator proof. |
| [T3 Code](https://github.com/pingdotgg/t3code), its contributors; [Compound Engineering](https://github.com/EveryInc/compound-engineering-plugin), Every and contributors | T3 Code provided the local coding/orchestration environment and external review route. The installed Compound Engineering skills guided planning, implementation, simplification and review; they do not replace executable validation or maintainer accountability. |

The full source pins are in [Eden-family profiles](adapters/eden-family/profiles),
[the Ryubing profile](adapters/ryujinx-family/profiles/ryubing.json), and the
qualification documents. This project does not redistribute every tool listed
above. Their inclusion describes actual use, not a blanket licensing grant.

## Reference material and research inputs

- [Dolphin](https://github.com/dolphin-emu/dolphin), Dolphin Emulator Project and
  contributors: source-built from emucap's pinned revision and patch stack for
  original GameCube/Wii Input Lab qualification. GPL-2.0-or-later; bundled
  dependencies retain their own notices. Build success and live guest results
  are recorded separately in the Input Lab qualification report.
- [melonDS](https://github.com/melonDS-emu/melonDS), melonDS team: inspected
  1.1 native input/touch/frame APIs and installed the official portable desktop
  build. GPL-3.0-or-later. The desktop GUI has installation/version proof only.
- [melonDS DS](https://github.com/JesseTG/melonds-ds), Jesse Talavera-Greenberg
  and contributors: built v1.4.0 at
  `f394adbacb5722ee97c1b37c8064da9a25818310`, using its pinned melonDS core and
  built-in replacement system files for original DS Input Lab qualification.
  GPL-3.0-or-later; bundled dependencies retain their own notices. emucap adds
  build identity and uses a shared supervised software libretro worker.
- [mGBA](https://mgba.io/), endrift and contributors: installed official 0.10.5
  portable desktop build, inspected Lua APIs, and built its libretro core at
  `26b7884bc25a5933960f3cdcd98bac1ae14d42e2` for original GBA Input Lab live
  qualification. The GUI has version proof; input/capture proof belongs to the
  separate core-based adapter. MPL-2.0; dependency notices remain separate.

- [Ozone](https://github.com/alula/Ozone), Alula and Atmosphère contributors:
  inspected as a GPLv2 research source for Ounce platform metadata, build recipes
  and its `npdmtool` invocation. It is not used here as a verified complete Switch 2
  firmware implementation.
- [SDL_GameControllerDB](https://github.com/mdqinc/SDL_GameControllerDB), its
  contributors: Ryubing's upstream startup code fetched controller-mapping
  metadata. The exact downloaded database revision was not separately recorded;
  it is not part of the original homebrew witness source.
- [MSYS2 MinGW-packages issue 2519](https://github.com/msys2/MINGW-packages/issues/2519):
  research input for MinGW emulated-TLS destructor behavior. The local teardown
  diagnosis additionally used actual reproductions and debugger evidence; the
  issue alone was not treated as proof of this project's failure.
- Upstream emulator sources and their bundled dependency notices supplied the
  API/lifecycle evidence for bridge hooks. Test captures are rendered by actual
  emulators running the source-built witnesses. Original witness source files
  [ctr.c](_tests/live/emulator-family/ctr.c) and
  [switch.c](_tests/live/emulator-family/switch.c) carry CC0-1.0 SPDX notices.
- Detailed evidence and limitations are preserved in
  [emulator-family qualification](docs/emulator-family-qualification.md),
  [native control recovery](docs/emulator-control-recovery.md),
  [Ounce packaging research](docs/switch2-ozone-research.md), and
  [Ryubing qualification](docs/ryubing-qualification.md).

## Attribution and redistribution boundaries

No affiliation with or endorsement by Nintendo, emulator maintainers, tool
authors, or AI providers is implied. Commercial games, proprietary firmware and
keys are not supplied by this work. A source build, metadata parse, successful
launch and verified guest control are different results.

Retain the existing [NOTICE](NOTICE), source-file licenses, corresponding sources
and bundled dependency notices when preparing distributions. An MIT upstream
frontend does not replace the GPL notice on this project's native bridge. This
record is not a completed legal review of a future combined binary package.

## Input Lab visual specimen artwork

The Pro Controller render in `docs/design/input-lab-preview.html` and the native
Input Lab raster UI (`_tests/input-lab/`) uses the
[shmove/gamepadviewer-procon](https://github.com/shmove/gamepadviewer-procon)
GamepadViewer skin, based on Open Joystick Display Project artwork by Anthony
Mattera (KernelZechs), copyright 2019–2020. Asset bytes are retained unchanged;
emucap adapts their composition and simulated input-state styling. This is a
design specimen, not native homebrew or qualified input-viewer integration.
The exact upstream revision, source paths and SHA-256 hashes are recorded in
`docs/design/assets/procon/provenance.json`. The full redistribution conditions
and disclaimer are retained in `docs/design/assets/procon/COPYRIGHT.md`.

This product includes software developed by "Open Joystick Display Project and
'Anthony Mattera' (http://www.ojdproject.com/)."

Inclusion does not imply endorsement or affiliation with those authors or Nintendo.

Input Lab's native raster conversion uses
[resvg-py](https://github.com/baseplate-admin/resvg-py), baseplate-admin and
contributors, version 0.5.0 (MIT), and its resvg dependencies, plus
[Pillow](https://python-pillow.github.io/), Pillow contributors (HPND/PIL-derived
license). These are build/test tools; their use does not replace the artwork's
terms. Original Input Lab C programs and bitmap glyphs carry CC0-1.0 notices.
Linked devkitPro runtime libraries retain their own licenses. Cross-building a
port does not qualify its emulator input or physical hardware behavior.

## AI usage disclosure

OpenAI Codex assisted research, planning, source implementation, debugging,
tests, build automation, documentation and local review for this emulator
integration. Anthropic Claude, reached through T3 Code, supplied an independent
adversarial code review. Its provider was attested; the precise served model was
not independently confirmed. AI-assisted code includes the bridge glue,
qualification harnesses and original test-witness implementation. The later
DS/GBA setup and Dolphin Input Lab changes used OpenAI Codex and its five
read-only simplification lenses; the historical Claude review does not cover
that later change set.

AI output is reviewed and tested; generation alone is not acceptance evidence.
This work records automated source review and reproducible checks, without
claiming that a human has reviewed every line. Technical claims require source
provenance and executable evidence. Hypotheses remain labeled, and formal models
or static checks do not establish unstated empirical runtime assumptions.
Maintainers remain responsible for licensing, testing, releases and policy
compliance.

Release and submission descriptions should retain an equivalent prominent AI
disclosure. GitHub's current
[Synthetic Media and AI Tools policy](https://docs.github.com/en/site-policy/acceptable-use-policies/github-synthetic-media-and-ai-tools)
addresses prohibited uses; this credits file does not certify compliance with
that or any future distribution policy. GitHub's
[Review AI-generated code guidance](https://docs.github.com/en/copilot/tutorials/review-ai-generated-code)
emphasizes functional validation and human oversight. These sources were checked
on 2026-11-04; a release must check the applicable current policies again.

## Keeping this record current

Update these credits when sources, dependencies, tools, AI providers or their
roles change, and when an evaluated tool becomes qualified or a prior claim is
invalidated. At release, reconcile this file with NOTICE, lockfiles, source
profiles, fixture manifests and qualification records. Preserve relevant
historical attribution without presenting superseded work as the current target.

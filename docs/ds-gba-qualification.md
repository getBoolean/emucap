# DS/GBA setup and Dolphin input qualification

Verified locally on Windows, 2026-11-04. This completes the requested portable
melonDS/mGBA setup and opt-in core control, plus the GC/Wii digital input runs.
It does not complete the broader all-platform Input Lab project.

## Installed applications and automation builds

- Desktop melonDS 1.1: `B:/tools/emucap/melonDS-1.1/melonDS.exe`, isolated
  `portable/` directory. Help/version checked; its Qt window is not controlled
  by this adapter. Archive SHA256 matched the official GitHub asset digest.
- Desktop mGBA 0.10.5:
  `B:/tools/emucap/mGBA-0.10.5/mGBA-0.10.5-win64/mGBA.exe`, upstream portable
  configuration retained. Version/help checked. The official asset published
  no checksum; its locally recorded digest is not an upstream digest match.
- Automation melonDS DS v1.4.0:
  `B:/tools/emucap/libretro/melonds/melondsds_libretro.dll`, source
  `f394adbacb5722ee97c1b37c8064da9a25818310`.
- Automation mGBA 0.10.5:
  `B:/tools/emucap/libretro/mgba/mgba_libretro.dll`, source
  `26b7884bc25a5933960f3cdcd98bac1ae14d42e2`.
- Dolphin NoGUI/Qt: `B:/dev/build/emucap-dolphin-input-lab/Binary/x64/`, source
  `409881c34357d0f105fd473167d15ab0bd9c1628`; patchset
  `92174033977016b038a39a38bd708a67ee2015fa1a862e8fcaf2d73a034bb993`.

The two automation cores share the existing bounded ABI loop, software capture,
supervised lifecycle and authenticated managed transport. Their embedded source
profiles must match their sidecars. Explicit `emulator.fork` / `emulator.core`
selection routes DS/GBA to `software_libretro`; default DS/GBA selection still
uses DeSmuME/Mesen2. See [build, selection and capability instructions](../adapters/libretro/README.md).

## Live proof

Evidence root: `C:/Users/Boolean/AppData/Local/Temp/emucap-input-lab/`.
Every row below used an original source-built Input Lab guest, verified its
embedded build identity, CRC, fresh sample and complete controller state, and
reported a completed owned stop. All five runner processes exited zero.

| Runtime / target | Accepted checkpoints | Final evidence directory |
| --- | ---: | --- |
| melonDS DS / DS | 49 | live-melonds-final-002 |
| mGBA / GBA | 37 | live-mgba-final-002 |
| Dolphin / GC | 41 | live-dolphin-gamecube-raw-002 |
| Dolphin / Wii | 38 | live-dolphin-wii-raw-002 |
| Azahar / 3DS regression | 100 | live-azahar-shared-final-002 |

DS/GBA test every advertised button's hold, sustained hold and release, combined
controls, and unsupported requests preserving the prior state. DS additionally
tests all four touch corners, centre, combined touch/buttons and release. Missing
required touch/axes/buttons now fails qualification instead of skipping cases.
GC/Wii verify all four panels together and require no leakage to other ports.
These counts are observation checkpoints, not independent features or proof of
deterministic execution. The full current nine-configuration evidence table is
in [Input Lab qualification](input-lab-qualification.md).

`qualified-expansion-identities.json` binds the final result files. Core results
also retain SHA256 identities for MCP, supervisor, core, sidecar and both worker
sources. `setup/libretro-install.json` records installed core identities;
portable application receipts and build logs are also under `setup/`.

## Checks and resolved failures

- `cargo test --lib --bin emucap-mcp -- --test-threads=4`: 1,922 passed,
  four explicitly ignored. A prior concurrent attempt hit a broker test's
  200 ms attach timeout; its isolated rerun and final complete suite passed.
  This report does not classify that observation as a proven pre-existing bug.
- `cargo clippy --lib --bin emucap-mcp --bin emucap-azahar -- -D warnings`,
  `cargo fmt --all --check`, Python compilation and `git diff --check`: passed.
- Input Lab host tests: nine passed. Software-core tests: three passed.
  Existing Azahar worker/native ABI tests: 21 passed, including GCC 16.
- All ten `_tests/emulator-bridges/fast.py` lanes passed on native Windows/GCC
  16. Final report: `fast-all-final/fast-results.json`. These synthetic ABI and
  protocol checks are separate from the live rows above. No remote CI ran.
- Dolphin originally timed out because CPU-written framebuffer guests emit no
  GX frame-end event to flush screenshot readback. The new patch flushes a
  pending screenshot at presentation. Subsequent stretched captures failed the
  native-size oracle; managed launch now selects the actual `Graphics` CLI
  namespace and raw-XFB resolution. Failed attempts are retained.
- Native diagnostic loss and a Ryujinx test environment mismatch reproduced
  from archived `174c1a2` source, without a worktree or changes to the checkout.
  Python's UCRT and MinGW's MSVCRT keep separate descriptor/environment tables.
  The worker now redirects native stdout too. The C ABI test now explicitly
  updates and reads back the native CRT environment before testing rejection;
  all original rejection assertions remain. No Ryujinx native code changed.
  [Microsoft's CRT documentation](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/getenv-wgetenv?view=msvc-170)
  describes the runtime-owned environment copy.
- Five read-only simplification lenses covered reuse, quality, efficiency,
  tests and comments. They found the capability-skipping defect; it was fixed
  with regression coverage. This is not a final shipping review of the entire
  unfinished all-platform Input Lab change set.

## Limits and local state

The stock desktop applications have installation/version proof; live control
proof belongs to their separate core builds. No exact step/pause/timed tap is
advertised by the cores. DS has persistent single touch; GBA has no touch/axes.
DSi, GB/GBC, microphone, link/network play, external storage-image selection,
desktop GUI automation, Linux/macOS live runs and physical hardware are outside
this qualification. Dolphin's public analog/trigger injection and Wii IR or
extensions remain unsupported/unqualified. No commercial ROM, original BIOS,
firmware or keys were acquired. Existing unrelated WIP was preserved. Nothing
was committed, pushed or submitted as a PR.

The reusable pieces are already repository components: the shared core worker
and build helper, explicit fork selection, the capability-presence regression,
and live pixel-oracle runners. They remain local and uncommitted. No additional
personal skill or memory update was created; existing testing/credits guidance
already covers the general process.

## Changed paths for this setup/control work

New:

- `adapters/libretro/.gitignore`
- `adapters/libretro/README.md`
- `adapters/libretro/bridge.py`
- `adapters/libretro/build.py`
- `adapters/libretro/test_bridge.py`
- `adapters/dolphin/patches/FrameDumper-vi-screenshot-flush.patch`
- `_tests/input-lab/qualify_dolphin.py`
- `_tests/input-lab/test_capabilities.py`
- `docs/ds-gba-emulator-options.md`
- `docs/ds-gba-qualification.md`

Changed, including updates to inherited untracked Input Lab files:

- `.github/workflows/emulator-bridge-validation.yml`
- `CREDITS.md`
- `NOTICE`
- `README.md`
- `_tests/emulator-bridges/fast.py`
- `_tests/input-lab/README.md`
- `_tests/input-lab/qualify.py`
- `adapters/azahar/bridge.py`
- `adapters/dolphin/README.md`
- `adapters/dolphin/upstream.lock`
- `adapters/ryujinx-family/tests/native_abi_test.py`
- `contracts/exceptions.json`
- `docs/input-lab-qualification.md`
- `src/azahar_host.rs`
- `src/bin/emucap-azahar.rs`
- `src/bin/emucap-mcp/args.rs`
- `src/bin/emucap-mcp/launch/emulator_family.rs`
- `src/bin/emucap-mcp/launch/plan.rs`
- `src/bin/emucap-mcp/launch/run.rs`
- `src/bin/emucap-mcp/launch/system.rs`
- `src/contracts_tests.rs`
- `src/emulator_profile.rs`
- `src/emulator_profile_tests.rs`
- `src/launch/emulator_family.rs`
- `src/launch/spec.rs`
- `src/launch/spec_tests.rs`

The earlier Input Lab art, native ports, plans, workflow and Eden Pro Controller
changes remain present; the list above does not relabel them as new DS/GBA work.

## Screenshot rerun

The later requested live run is linked in `docs/input-lab-qualification.md`.
Screenshot inspection found a GBA visual defect that the earlier input-only
checks missed. The original GBA source now stages drawing in EWRAM and publishes
at VBlank; native DS was also rebuilt because the source is shared. Fresh DS/GBA
runs pass 49/37 checkpoints with mandatory title/sample-label validation. Ten
host tests now pass. Additional changed paths for that correction are
`_tests/input-lab/handheld.c`, `_tests/input-lab/observation.py` and
`_tests/input-lab/test_observation.py`; the live runner invokes the new check.
Earlier input-only evidence above remains historical, not a visual pass.

# Experimental Eden-family bridge

One native SDL producer serves Eden, Eden-NX2, Eglantine, and compatible forks.
Per-pin patches connect it to lifecycle, VirtualGamepad, touchscreen, renderer
capture and managed storage. No keyboard replay or window automation is used.

| Selection | Source branch | Pinned revision | Declared systems |
| --- | --- | --- | --- |
| `eden` | `master` | `5df599128d6828fa0e42968909da848c255d22b1` | Switch |
| `eden-nx2` | `eden-nx2` | `50fa86bbbc403ad565eb44fcc281f16f77c69e15` | Switch, Switch 2 |
| `eglantine` | Djihads80/Eglantine `nx2` | `c54bc2289bfffda7fa3cc4c3a8cf522d84a10fd4` | Switch, Switch 2 |

Declared systems describe source intent and admission, not live qualification.
The default Eden-NX2 `master` branch is not the experimental target. Eglantine
uses the [requested repository](https://github.com/Djihads80/Eglantine).
Its README compatibility claims are upstream claims; emucap has not reproduced
them. See the [measured evidence and blockers](../../docs/emulator-family-qualification.md).

## Build

Install the selected upstream's native dependencies, a recent CMake (Eden requires
3.31+), Ninja and C++ toolchain. Run from the emucap checkout:

```sh
python3 adapters/eden-family/build.py --fork eden --jobs 2
python3 adapters/eden-family/build.py --fork eden-nx2 --jobs 2
python3 adapters/eden-family/build.py --fork eglantine --jobs 2
```

On Windows use `py -3.12` or `build.ps1`; `build.sh` is a Unix wrapper. `--cmake`,
`--source`, `--output`, `--target`, and repeatable `--cmake-arg=-D...` select
explicit build inputs. `--prepare-only` applies checked patches and generates
identity; it is not a build pass. Existing source edits beyond the exact patch
are rejected, never reset. Defaults place `eden-sdl[.exe]` and the matched
`emucap-emulator-build.json` under `build/<fork>/bin/`.

Compatible custom forks use `--profile source-descriptor.json --patch integration.patch`.
The descriptor supplies fork, repository, full revision, systems and renderers;
adapt the integration hooks for that exact source. Reuse `native/` instead of
copying an adapter. Build metadata is compiled into the executable and compared
with the selected sidecar at runtime. Editing a sidecar cannot add support.

The executable's `--emucap-build-profile` query returns its compiled profile and
exits before constructing the guest or applying configuration. Managed preflight
uses a bounded query before replacing a live generation, then verifies native
hello and effective storage again after launch.

## Managed launch

Pass the same `emulator` selection to `launch_plan` and `launch`:

```json
{"system":"switch","content_path":"/absolute/witness.nro","emulator":{"fork":"eden","binary":"/absolute/eden-sdl","renderer":"vulkan"}}
```

Select `switch2` explicitly for a lawful target fixture. A loose ExeFS entry
`main` requires `main.npdm` and a reviewed loader-visible graph; use the exact
indirect-media approval returned by `launch_plan`. Metadata, companion modules
and sibling RomFS participate in identity and staging. Renaming a Switch NRO or
selecting `switch2` is not evidence that it targets Switch 2.

An empty sibling RomFS root or nested directory is currently rejected before
admission because file-member staging cannot preserve that topology. It is not
silently omitted or treated as equivalent content.

`profile` can select a sidecar; `config` copies one explicit INI into the private
generation. The process reports its actual managed root and build identity before
launch becomes current. It does not import the normal user's profile. `EMUCAP_EDEN_BIN`
is an optional executable default. Stop with the current `runtime_instance.launch_id`.

## Controls and headless use

Digital buttons, two sticks and single-contact touchscreen holds use native
input objects on their owner thread. Empty buttons/axes release controller
state; `release_touch` releases touch independently. Broker disconnect clears
both. Running waits have keyed cancellation and preserve unrelated persistent
input. Exact frame stepping and timed `tap` are absent.

Managed mode fixes one connected Pro controller at native Player1/virtual port0,
undocked mode and enabled touchscreen. It clears primary keyboard/SDL/motion
bindings from supplied config; the dedicated virtual input callbacks remain
bound. Other controller styles and handheld-only fixtures remain unqualified.

`wait_for_running_frames` counts `native_render_present`: native compositor
present events, with actual delta and overshoot. It neither pauses nor resumes
the guest and is not a guest-frame or determinism guarantee. Capture owns its
pixel buffer through the renderer callback; a frozen capture uses the last
completed capture and reports freshness.

Vulkan/OpenGL need a working GPU API and often a display even with `display:false`.
On Linux use a qualified Mesa/Vulkan driver and Xvfb for the hidden SDL window;
set `VK_ICD_FILENAMES` only to a real installed ICD. A null renderer cannot
qualify capture. Unsupported drivers or missing display dependencies fail the
lane. OpenGL/Vulkan and visible/hidden runs are separate evidence cells.

## Check

```sh
python3 adapters/eden-family/tests/run.py
python3 -m unittest discover -s adapters/eden-family/tests -p 'test_*.py'
```

The runner compiles native regression/endpoint fixtures and tests real loopback
authentication, capture bytes, input hooks, cancellation and detach. Its hooks
are synthetic. Only the [lawful guest harness](../../_tests/live/emulator-family/README.md)
can establish emulator/guest behavior for a particular build and renderer.

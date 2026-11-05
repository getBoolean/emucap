# Ryujinx-family source adapter

Build the pinned Ryubing Switch 1 headless frontend together with emucap's
native authenticated bridge. The maintained source revision is recorded in
`profiles/ryubing.json`; upstream MIT notices are preserved in the source patch.
Switch 2, deterministic stepping, exact timed taps, Home and Capture are absent.

The source recipe supports Windows/Linux x86_64. On Windows install .NET 10 SDK
and an x86_64 MinGW C++20 compiler. On Linux use .NET 10 SDK and GCC C++20;
SDL/Vulkan/OpenGL still need working host display and driver libraries. The published
application is framework dependent and requires .NET 10. Keep its complete output
folder together, including `emucap-native.dll` and every managed/runtime DLL.

```powershell
./adapters/ryujinx-family/build.ps1 --fork ryubing --cxx B:/tools/mingw64/bin/g++.exe --jobs 8
```

The recipe downloads the pinned source and SHA-256-pinned nlohmann/json 3.12.0
single header when missing; the verified header participates in the build digest.
Use `--source PATH`, `--output PATH`, and `--json-include PATH` to reuse explicit
locations. `--json-include` must contain that exact amalgamated `nlohmann/json.hpp`,
rather than the multi-file include tree (use upstream's `single_include` directory).
Existing source edits must exactly match the selected patch; unrelated
tracked or untracked edits are rejected. Default executable:
`adapters/ryujinx-family/build/ryubing/bin/Ryujinx.exe`.
A custom fork requires both `--profile fork.json --patch fork.patch`, with the
same profile fields as the maintained profile and an exact source revision.
To launch a custom fork, pass its explicit `emulator.binary` or `emulator.profile`;
the fork name alone does not select the Ryujinx family for unknown forks. The
`EMUCAP_RYUJINX_BIN` override applies after that family selection.
The recipe verifies the embedded profile before publishing the admission sidecar.

Managed launch creates and selects the generation root before initialization.
It uses only that root's keys, files and default configuration; updater/Discord
initialization and executable-adjacent config import are disabled. The optional
`emucap-config.json` within the generation root accepts these optional fields:

```json
{"preferred_gpu_vendor":"Intel"}
```

`memory_manager_mode` accepts `SoftwarePageTable`, `HostMapped`, or
`HostMappedUnsafe`; omitted fields retain upstream defaults. Linux Docker live
qualification uses `{"memory_manager_mode":"SoftwarePageTable"}` because the
default host-mapped mode aborts in this environment. Set
`DOTNET_EnableAlternateStackCheck=1` in the Linux MCP server environment, matching
the pinned upstream Linux launcher. This does not qualify other memory modes.

The frontend verifies the native library's SHA-256 against its compiled constant
before either `--emucap-build-profile` or native use. Its identity reports the
actual renderer, Switch 1 system, source content file and effective root. Loose
ExeFS uses the containing directory for the upstream CLI and the actual `main`
file for native content identity. Build/profile probing performs no guest run.

Input is persistent, published on every HID update to one undocked Pro Controller
on player one. It accepts eighteen buttons including SL/SR, four signed stick
axes with circular clamping, and one touch contact across 1280×720 coordinates.
Touch uses Start/held/End/empty reports. Physical polling cannot overwrite managed
button/touch state.

Capture uses the renderer's synchronous ScreenCaptured event, with bounded data
copied into the native bridge and channel/flip normalization performed there.
Progress counts actual GL swaps and successful Vulkan presentations, including
threaded-renderer forwarding. It measures observed presentation, not guest
execution or GPU completion. Native stop releases input while owner state remains
alive; the native handle and delegates survive HLE disposal and renderer shutdown.

Verification requires a lawful homebrew fixture with a valid standard NACP
metadata asset. A successful build or synthetic native test does not establish
live homebrew control. No firmware, keys or commercial content are supplied.

See [recorded qualification and limits](../../docs/ryubing-qualification.md) and
the [live harness](../../_tests/live/emulator-family/README.md). For MCP launch,
select `system: "switch"` and `emulator: {"fork":"ryubing", "binary":"/path/to/Ryujinx"}`
in both `launch_plan` and `launch`. Optional config and renderer belong in that
same `emulator` object. Use persistent holds/releases and observed progress waits
from the connected `status`; pause capture returns the cached completed image.
Capture before pausing if an image is needed: without a completed requested
capture, paused screenshot is unavailable. Pause is execution state and persists
across attachment changes; reconnect does not implicitly resume the guest.
The advertised `ryujinx.execution-pause.scheduler-state` contract variation
means successful pause acknowledges the native scheduler's paused state.
Responses and status report `frozen: false`: this boundary does not guarantee
that all in-flight work has drained or that free progress is excluded.

Maintained source pins are read from `profiles/ryubing.json` by the build recipe
and embedded from that same descriptor by Rust admission. Exact applied-patch
verification lives in `adapters/_common/build_support.py`; family-specific
untracked-file policy stays in the recipe.

The shared native capture worker has a bounded queue. Renderer completion owns
and normalizes pixel bytes, then queues PNG encoding; it does not encode under
the native handle lock. Stop prevents publication and closes the queue without
waiting for active encoding; bridge destruction joins the worker. Native error
messages cross the managed boundary through a bounded UTF-8 buffer.

Run the managed diagnostic regression separately from native ABI or live tests:

```powershell
dotnet run --project adapters/ryujinx-family/tests/managed-errors/managed-errors.csproj --configuration Release
```

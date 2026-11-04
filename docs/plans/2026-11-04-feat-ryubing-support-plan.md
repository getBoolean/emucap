# Ryubing support

## Goal

Add the maintained Ryubing source as a distinct Ryujinx-family backend in the
existing checkout. Launch, inspect captures, control persistent gamepad/touch
input, wait for observed presentation progress, and stop a managed process.
Keep executable/config selection and live build/root/content binding explicit.
The canonical source is `https://git.ryujinx.app/projects/Ryubing.git`, master
revision `a61a42681119bf15fe8f3297677ae48bda83e70f`.

The current source implements Switch 1. Switch 2 machine support was not found;
Switch 2 controller recognition does not establish it. Reject Switch 2 selection.
No commercial assets, firmware or keys are acquired. Do not edit 3ds_flutter,
create a worktree, push or open a PR.

## Integration decisions

- Reuse emucap's existing authenticated native transport and owner-thread queue.
  A thin versioned C ABI lets the .NET frontend invoke that C++ implementation;
  avoid writing a second authentication, cancellation or capture protocol in C#.
- Keep the source adapter under `adapters/ryujinx-family`, with a pinned Ryubing
  profile, source patch and build recipe. The DLL and .NET executable stay together.
  Compile the source profile into the frontend and verify the native DLL's hash
  before probing/using it, so an ignored or stale dependency is not silently used.
- Generalize only the shared transport fields Ryubing needs: family/adapter
  identity, allowed button mask, touch bounds, dynamic capture dimensions and
  optional native pause/resume hooks. Preserve Eden behavior and wire compatibility.
- Input accepts the first eighteen shared buttons (including SL/SR), four signed
  stick axes, and one touch contact. Home/Capture are absent in the source HID
  enum and must be rejected rather than cast into stick-direction bits.
- Pump bridge effects in the SDL main owner loop. Override input every HID
  update; a one-time write would be overwritten by physical input polling.
- Count actual GL swap and successful Vulkan QueuePresent calls in the graphics
  backend, forwarding through the threaded renderer. Counting after a queued
  PresentFrame call or in the empty Vulkan SwapBuffers callback is insufficient.
  This is observed presentation progress, not a guest-frame or GPU-completion
  guarantee. Exact stepping and exact timed input remain unsupported.
- Capture through the renderer's ScreenCaptured event. Copy bounded data during
  the synchronous callback and normalize RGBA/BGRA and both flip axes. Retain
  managed delegates and native ownership until renderer callbacks have ceased.
- Stop native service/input while owner state is alive; destroy the C ABI handle
  after GPU workers finish. Never call blocking WindowBase.Exit from its main
  owner loop. Use the existing unwind with a nonblocking stop request if needed.
- Create and verify the generation root before initialization. Explicitly use
  only its config and filesystem roots; do not import executable-adjacent or
  installed-user config/keys/mods. Native readback reports the effective root.
- Pause/resume may be exposed only when the Horizon activity/tick-source operation
  and its runtime behavior are verified. Do not implement resume-count-pause as
  deterministic stepping.

## Implementation units

1. Share the native bridge across runtimes. Add the versioned C ABI and focused
   native tests; verify existing Eden endpoint behavior and Ryujinx-specific
   identity/button/bounds/capture behavior. Commit this prerequisite before its
   consumers. Authoritative verification belongs to the root agent.
2. Register the Ryujinx family in Rust launch selection, schemas, content identity,
   capability contracts, system catalog and packaging. Reuse managed supervision
   and native identity validation. Keep explicit custom-fork profiles possible.
3. Patch and build the Ryubing SDL headless source, consuming the committed C ABI.
   Units 2 and 3 may run together only with disjoint file ownership and a fixed
   ABI/profile contract. The root owns package installs, full builds and git.
4. Qualify actual homebrew, update opt-in live/CI documentation and execute review.
   Preserve earlier Eden/Azahar proof, and distinguish build/protocol/live results.

## Verification

- Baseline canonical .NET 10 source build before source changes.
- Native C ABI boundary tests: authenticated actual loopback endpoint, exact
  family identity, unsupported Home/Capture rejecting before mutation, configured
  touch bounds, capture dimensions/channel/flip conversion, and safe late capture
  after stop. These remain synthetic protocol evidence.
- Rust tests for maintained/custom family selection, Switch 2 rejection, matching
  executable/profile/DLL admission and content/config staging.
- .NET interop compile plus actual full frontend build using the pinned source.
- Actual lawful Switch 1 homebrew witness: native identity/root/content, changing
  guest pixels/counter, input/release, touch/release, cancellation, replacement
  rejection preserving generation and verified managed exit. Repeat clean launches.
- Additional pause/frozen capture checks only if native pause is advertised.
- Existing six fast lanes, appropriate Rust dependent tests, schema generation
  checks, lint, diff check, and a completed review receipt.

## Done

The user can select the Ryubing build/config through emucap and control the live
homebrew guest. Exact changed paths, source/build identities, checks and genuine
blockers are recorded. Missing prerequisites or unsupported operations fail
honestly; unit/build success never substitutes for actual live control.

# Pico emulator packages

This fork adds the optional `nds_storage_image` managed-launch argument to
emucap 1.1.0. It publishes Windows x86-64 and Linux x86-64 core and native
DeSmuME packages. Starting with `1.1.0-pico.2`, the native adapter also corrects
CompactFlash command-register status reads required by Pico Loader startup.
Starting with `1.1.0-pico.4`, it preserves halfword-aligned Thumb addresses on
LDM exception returns. The prior alignment could replay an interrupted PUSH,
corrupt the ARM7 stack and leave recursive searches waiting forever for card I/O.
The native build runs 128 instruction-handler regressions before packaging.
The earlier pico.3 tag did not publish: its new Windows regression executable
needed the SDL entry point. Tags remain immutable.
Install both package trees with their complete runtime dependencies and licenses.

`feat/nds-storage-image` follows recorded upstream main commit
`da7a2e76f37173e15c8d370844f28c4ffe542a5a` and contains only the generic feature,
its tests and documentation. It is the branch for a future upstream contribution.

`pico/1.1.0-storage` starts at upstream release commit
`8587968a5e77acb51fdd76caa2bf04d17ce56082`, backports the generic feature and
contains fork versioning, packaging and compiler compatibility fixes. Keep those
changes out of the contribution branch.

The release workflow requires an existing tag at the dispatched revision, runs
the shared core tests and package smoke checks on both native hosts, and builds
the locked native adapter on Windows and Linux. Publication waits for every
build to succeed. Each native package includes its source revision, upstream
revision, patchset identity, file hashes and licenses. Matching native source
archives retain the patched upstream tree and build recipes. Release checksums
identify every core, native runtime and source archive.

The fork's native workflow uses archive checksums and extracted file manifests;
it does not claim the upstream release pipeline's signed provenance.

The image must be owned exclusively by the caller. Managed stop forcibly ends
DeSmuME, so completed guest writes require a confirmed subsequent card read before
using the stopped image as a persistence checkpoint. A failed session's raw image
may still contain buffered-write gaps.

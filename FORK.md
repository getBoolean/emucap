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

Storage support, native compatibility fixes and fork packaging are now merged
into `main`. The former feature and packaging branches have been retired.
The original generic contribution, without fork packaging changes, remains
available at commit
[`3c66d9c`](https://github.com/getBoolean/emucap/commit/3c66d9cc7dc08dd05f92d40d56113ccdb8e9932b).

The **Release Pico emulator packages** workflow (`release-pico.yml`) requires
an existing tag at the dispatched revision, runs
the shared core tests and package smoke checks on both native hosts, and builds
the locked native adapter on Windows and Linux. Publication waits for every
build to succeed. Each native package includes its source revision, upstream
revision, patchset identity, file hashes and licenses. Matching native source
archives retain the patched upstream tree and build recipes. Release checksums
identify every core, native runtime and source archive.

The upstream **Release binaries** workflow (`release-core.yml`) retains its
verified publication-recovery support and three-platform core validation.
Pico packages use their separate Windows/Linux validation workflow.

The fork's native workflow uses archive checksums and extracted file manifests;
it does not claim the upstream release pipeline's signed provenance.

The image must be owned exclusively by the caller. Managed stop forcibly ends
DeSmuME, so completed guest writes require a confirmed subsequent card read before
using the stopped image as a persistence checkpoint. A failed session's raw image
may still contain buffered-write gaps.

# Pico storage core

This fork adds the optional `nds_storage_image` managed-launch argument to
emucap 1.1.0. It publishes Windows x86-64 and Linux x86-64 core packages.
Native DeSmuME packages remain the official emucap 1.1.0 releases and must be
installed separately with their complete runtime dependencies and licenses.

`feat/nds-storage-image` follows recorded upstream main commit
`da7a2e76f37173e15c8d370844f28c4ffe542a5a` and contains only the generic feature,
its tests and documentation. It is the branch for a future upstream contribution.

`pico/1.1.0-storage` starts at upstream release commit
`8587968a5e77acb51fdd76caa2bf04d17ce56082`, backports the generic feature and
contains fork versioning, packaging and compiler compatibility fixes. Keep those
changes out of the contribution branch.

The release workflow requires an existing tag at the dispatched revision, runs
the shared core tests and package smoke checks on both native hosts, and publishes
only after both builds succeed. Each core package includes its source identity,
binary hashes and licenses; release checksum files identify the archive bytes.

The image must be owned exclusively by the caller. Managed stop forcibly ends
DeSmuME, so completed guest writes require a confirmed subsequent card read before
using the stopped image as a persistence checkpoint. A failed session's raw image
may still contain buffered-write gaps.

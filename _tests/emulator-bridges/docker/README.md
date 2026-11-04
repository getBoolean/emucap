# Linux validation with Compose

Both services have explicit container names and folder bind mounts. The checkout,
upstream source and lawful fixture are read-only; caches and evidence use separate
host folders. Missing bind folders fail instead of being created implicitly.
No named Docker volumes or published ports are used. Large source/build trees,
NuGet/Rust/Python downloads and compiler temporary files remain in the mounted
work folder. Private guest runtime files use ephemeral Linux `/tmp` so that
their permission checks exercise the Linux filesystem.

Set absolute paths for `EMUCAP_REPO_ROOT`, `EMUCAP_RYUBING_SOURCE`,
`EMUCAP_SWITCH_FIXTURE`, `EMUCAP_DOCKER_EVIDENCE` and `EMUCAP_DOCKER_WORK` in the
calling environment or a private Compose `--env-file`. The upstream checkout must
match the maintained Ryubing revision. The fixture is the original Switch 1
`build_fixture.py` NRO with NACP metadata. Create `fast` and `native` beneath the
evidence folder, and `fast` and `native` beneath the work folder, before starting.

```sh
docker compose -f _tests/emulator-bridges/docker/compose.yml config --quiet
docker compose -f _tests/emulator-bridges/docker/compose.yml up -d fast
docker compose -f _tests/emulator-bridges/docker/compose.yml exec -T fast bash /workspace/_tests/emulator-bridges/docker/fast.sh
docker compose -f _tests/emulator-bridges/docker/compose.yml up -d --build ryubing
docker compose -f _tests/emulator-bridges/docker/compose.yml exec -T ryubing bash /workspace/_tests/emulator-bridges/docker/ryubing.sh
```

`fast` is synthetic ABI/protocol proof. `ryubing` builds the pinned frontend and
Linux MCP, then runs the actual homebrew witness as a non-root user under Xvfb
with Mesa software Vulkan. A missing tool, failed build or failed guest check is
fatal. Check `docker-result.json` and the guest `result.json`; a container starting
or an emulator surviving does not establish qualification. This is opt-in local
validation; it does not represent a remote GitHub Actions result. The named
services stay available for diagnostics. Use this same Compose file's `down`
when finished; bind data survives and is not deleted by that command.

The guest run explicitly selects `SoftwarePageTable` in its recorded config and
uses upstream's Linux alternate-stack runtime flag. Default host-mapped memory
aborts in this Docker environment and is not qualified by the software-mode run.
Use a fresh evidence output folder for each complete run; guest evidence is never
overwritten in place.

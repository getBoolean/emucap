"""Package public source, core and adapter host binaries; smoke-test the extracted payload."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import tomllib
import zipfile

CORE = ("emucap", "emucap-mcp", "emucap-track-mcp", "emucap-broker")
AZAHAR_RESOURCES = ("adapters/azahar/bridge.py",)


def azahar_payload(root, suffix):
    required = ("target/release/emucap-azahar" + suffix, *AZAHAR_RESOURCES)
    for relative in required:
        if not (root / relative).is_file():
            raise RuntimeError(f"Missing Azahar package resource: {relative}")
    return {
        "resources": {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                      for path in AZAHAR_RESOURCES},
        "python": {"minimum_version": "3.12", "bundled": False},
        "core": {"bundled": False, "build_profile_required": True},
    }


def smoke_azahar_worker(root, scratch):
    if sys.version_info < (3, 12):
        raise RuntimeError("Azahar package validation requires a real Python 3.12+ executable")
    worker = root / "adapters/azahar/bridge.py"
    command = [sys.executable, "-I", "-u", str(worker)]
    result = subprocess.run([*command, "--help"], capture_output=True, text=True, timeout=15)
    if result.returncode or "--core" not in result.stdout:
        raise RuntimeError(f"Extracted Azahar worker help failed: {result.stderr}")
    scratch.mkdir(parents=True, exist_ok=True)
    content = scratch / "synthetic-preflight.3dsx"
    content.write_bytes(b"package dependency preflight; not executable homebrew")
    missing_core = scratch / "missing-azahar-libretro"
    result = subprocess.run([*command, "--core", str(missing_core), "--rom", str(content),
                             "--directory", str(scratch / "azahar-user")],
                            capture_output=True, text=True, timeout=15)
    if not result.returncode or missing_core.name not in result.stderr:
        raise RuntimeError(f"Missing Azahar native core was not rejected: {result.stderr}")
    return {"worker_help": "passed", "missing_core": "rejected",
            "python_version": sys.version.split()[0],
            "proof_level": "extracted-worker-preflight"}


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, encoding="utf-8", **kwargs).strip()


def smoke(root, version, revision, scratch):
    suffix = ".exe" if os.name == "nt" else ""
    bindir = root / "target/release"
    env = dict(os.environ, EMUCAP_REGISTER_DRY_RUN="1", EMUCAP_PORT="0",
               EMUCAP_EMU_HOME=str(scratch / "home"), EMUCAP_TRACK_ROOT=str(scratch / "track"),
               EMUCAP_REPO_ROOT=str(root))
    env.pop("EMUCAP_BROKER", None)
    script = root / "tools" / ("register-codex-mcp.ps1" if suffix else "register-codex-mcp.sh")
    command = ["pwsh", "-NoProfile", "-File"] if suffix else ["sh"]
    output = run(*command, str(script), env=env)
    registered = [Path(line.split("->", 1)[1].strip())
                  for line in output.splitlines() if "->" in line]
    assert len(registered) == 2, output
    for name, actual in zip(CORE[1:3], registered):
        # PowerShell resolves Windows short names and case; compare file identity.
        assert (bindir / (name + suffix)).samefile(actual), output
    assert "Usage:" in run(str(bindir / ("emucap" + suffix)), "--help", env=env)
    evidence = {"emucap": {"help": "passed"}}
    azahar_payload(root, suffix)
    azahar = subprocess.run([str(bindir / ("emucap-azahar" + suffix))],
                            capture_output=True, text=True, env=env, timeout=15)
    if not azahar.returncode or "usage: emucap-azahar" not in azahar.stderr:
        raise RuntimeError(f"Extracted Azahar host usage failed: {azahar.stderr}")
    evidence["emucap-azahar"] = {"host_usage": "passed",
                                  **smoke_azahar_worker(root, scratch / "azahar-preflight")}
    for name in CORE[1:3]:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
            process = subprocess.Popen([str(bindir / (name + suffix))], cwd=scratch,
                                       env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=errors, text=True, encoding="utf-8")
            responses = queue.Queue()

            def read_lines():
                for line in process.stdout:
                    responses.put(json.loads(line))

            reader = threading.Thread(target=read_lines, daemon=True)
            reader.start()

            def request(number, method, params):
                process.stdin.write(json.dumps(dict(jsonrpc="2.0", id=number,
                                                     method=method, params=params)) + "\n")
                process.stdin.flush()
                while True:
                    response = responses.get(timeout=30)
                    if response.get("id") == number:
                        assert "error" not in response, response
                        return response["result"]

            try:
                initialized = request(1, "initialize", {
                    "protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "release-package-check", "version": "1"}})
                assert initialized["serverInfo"]["version"] == version, initialized
                process.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
                process.stdin.flush()
                catalog = request(2, "tools/list", {})
                assert catalog["tools"], catalog
                evidence[name] = {"serverInfo": initialized["serverInfo"],
                                  "tool_count": len(catalog["tools"])}
                if name == "emucap-mcp":
                    result = request(3, "tools/call", {"name": "status", "arguments": {}})
                    state = result.get("structuredContent")
                    if state is None:
                        state = json.loads(result["content"][0]["text"])
                    assert state["server_build"] == revision, state
                    assert state["connected"] is False, state
                    evidence[name]["server_build"] = state["server_build"]
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                reader.join(timeout=5)
                errors.seek(0)
                if process.returncode:
                    raise RuntimeError(errors.read())
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("source", "target", "version", "revision", "output"):
        parser.add_argument("--" + option, required=True)
    args = parser.parse_args()
    compiler = run("rustc", "-vV")
    assert f"host: {args.target}" in compiler, compiler
    source, output = Path(args.source).resolve(), Path(args.output).resolve()
    assert run("git", "-C", str(source), "rev-parse", "HEAD") == args.revision
    assert not run("git", "-C", str(source), "status", "--porcelain")
    assert tomllib.loads((source / "Cargo.toml").read_text(encoding="utf-8"))["package"]["version"] == args.version
    short = run("git", "-C", str(source), "rev-parse", "--short", "HEAD")
    suffix = ".exe" if args.target.endswith("windows-msvc") else ""
    name = f"emucap-{args.version}-{args.target}"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="emucap-release-") as temporary:
        temporary = Path(temporary)
        stage = temporary / name
        stage.mkdir()
        archive = temporary / "source.tar"
        subprocess.run(["git", "-C", str(source), "archive", "--format=tar",
                        "-o", str(archive), "HEAD"], check=True)
        with tarfile.open(archive) as packed:
            packed.extractall(stage, filter="data")
        bindir = stage / "target/release"
        bindir.mkdir(parents=True)
        digests = {}
        metadata = json.loads(run("cargo", "metadata", "--locked", "--no-deps", "--format-version", "1", cwd=source))
        package_metadata = next(p for p in metadata["packages"] if p["name"] == "emucap")
        binaries = sorted(t["name"] for t in package_metadata["targets"] if "bin" in t["kind"])
        assert set(CORE).issubset(binaries)
        assert "emucap-azahar" in binaries, "Azahar Rust host must be included in core packages"
        for binary in binaries:
            path = bindir / (binary + suffix)
            shutil.copy2(source / "target" / args.target / "release" / path.name, path)
            digests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest = dict(version=args.version, source_revision=args.revision,
                        target=args.target, binaries=digests,
                        azahar=azahar_payload(stage, suffix),
                        rustc=compiler)
        (stage / "CORE-BUILD.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (stage / "PREBUILT-CORE.md").write_text(
            "# Prebuilt emucap core\n\n"
            "Core and adapter host executables are in `target/release/`. Keep this directory tree intact.\n"
            "Run `sh tools/register-codex-mcp.sh` (macOS/Linux) or "
            "`pwsh -File tools/register-codex-mcp.ps1` (Windows), then reconnect both MCP servers.\n"
            "The Rust build step in AGENT_GUIDE.md can be skipped. Install the matching native "
            "emulator package separately. Firmware and games are supplied by the user.\n\n"
            "Azahar also requires a real Python 3.12+ executable matching the native core architecture "
            "and a separately built patched libretro core with its matching build profile. "
            "The stdlib-only private worker is `adapters/azahar/bridge.py`; Python and the native "
            "core are not bundled. Set explicit Python/core paths in the managed launch options. "
            "Package validation checks host/worker startup and missing-core rejection; it does not "
            "qualify live emulator or guest behavior.\n")
        if suffix:
            package = Path(shutil.make_archive(str(output / name), "zip", temporary, name))
        else:
            package = output / (name + ".tar.gz")
            with tarfile.open(package, "w:gz") as packed:
                packed.add(stage, arcname=name)
        extracted = temporary / "extracted"
        extracted.mkdir()
        if suffix:
            with zipfile.ZipFile(package) as packed:
                packed.extractall(extracted)
        else:
            with tarfile.open(package) as packed:
                packed.extractall(extracted, filter="data")
        manifest["validation"] = smoke(extracted / name, args.version, short, temporary)
        (output / (name + ".json")).write_text(json.dumps(manifest, indent=2) + "\n")
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        # sha256sum treats a CR from Windows text translation as part of the filename.
        (output / (name + ".sha256")).write_bytes(f"{digest}  {package.name}\n".encode("ascii"))
        print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

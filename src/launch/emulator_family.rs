//! Managed selection and process specifications for source-patched emulator families.
use super::{LaunchSpec, RuntimeEnv};
use crate::emulator_profile::{BuildProfile, EmulatorFamily};
use serde::{Deserialize, Serialize};
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Default, Deserialize, Serialize, schemars::JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct EmulatorOptions {
    /// Maintained fork (azahar, eden, eden-nx2, eglantine, ryubing), or an explicit custom profile's fork.
    pub fork: Option<String>,
    /// Patched SDL binary, or the Rust emucap-azahar supervisor for CTR.
    pub binary: Option<String>,
    /// Azahar libretro shared library; ignored paths on other systems are rejected.
    pub core: Option<String>,
    /// Real Python 3.12+ executable for the private Azahar worker.
    pub python: Option<String>,
    /// Explicit emucap-emulator-build/v1 JSON sidecar.
    pub profile: Option<String>,
    /// Optional isolated config: Eden INI or curated Ryujinx JSON, copied into the generation.
    pub config: Option<String>,
    /// software for CTR; vulkan or opengl for supported Eden-family and Ryujinx-family builds.
    pub renderer: Option<String>,
}

#[derive(Debug, Clone)]
pub struct ResolvedEmulator {
    pub binary: PathBuf,
    pub core: Option<PathBuf>,
    pub python: Option<PathBuf>,
    pub worker: Option<PathBuf>,
    pub profile_path: PathBuf,
    pub profile: BuildProfile,
    pub config: Option<PathBuf>,
    pub system: String,
    pub renderer: String,
}

fn invalid(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message.into())
}

fn regular(path: impl AsRef<Path>) -> io::Result<PathBuf> {
    let path = path.as_ref();
    crate::path_safety::open_regular_file_no_follow(path)?;
    path.canonicalize()
}

pub fn read_profile(path: &Path) -> io::Result<BuildProfile> {
    let file = crate::path_safety::open_regular_file_no_follow(path)?;
    if file.metadata()?.len() > 64 * 1024 {
        return Err(invalid("emulator build profile exceeds 64 KiB"));
    }
    let mut bytes = Vec::new();
    file.take(64 * 1024 + 1).read_to_end(&mut bytes)?;
    if bytes.len() > 64 * 1024 {
        return Err(invalid("emulator build profile grew beyond limit"));
    }
    let profile: BuildProfile =
        serde_json::from_slice(&bytes).map_err(|error| invalid(error.to_string()))?;
    profile.validate().map_err(invalid)?;
    Ok(profile)
}

fn selected_path(explicit: Option<&str>, env_key: &str, fallback: PathBuf) -> PathBuf {
    explicit
        .map(PathBuf::from)
        .or_else(|| std::env::var_os(env_key).map(PathBuf::from))
        .unwrap_or(fallback)
}

fn cpu_feature_available(feature: &str) -> bool {
    #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
    match feature {
        "sse2" => return std::is_x86_feature_detected!("sse2"),
        "sse4.1" => return std::is_x86_feature_detected!("sse4.1"),
        "cmpxchg16b" => return std::is_x86_feature_detected!("cmpxchg16b"),
        "sse4.2" => return std::is_x86_feature_detected!("sse4.2"),
        "avx" => return std::is_x86_feature_detected!("avx"),
        "avx2" => return std::is_x86_feature_detected!("avx2"),
        "avx512f" => return std::is_x86_feature_detected!("avx512f"),
        _ => (),
    }
    cfg!(target_arch = "aarch64") && feature == "neon"
}

fn probe_output(mut command: Command, limit: usize, label: &str) -> io::Result<Vec<u8>> {
    command
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000);
    }
    let mut child = command
        .spawn()
        .map_err(|error| invalid(format!("{label} prerequisite unavailable: {error}")))?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| invalid(format!("{label} probe has no output channel")))?;
    let (tx, rx) = std::sync::mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let mut output = Vec::new();
        let result = stdout
            .take(limit as u64 + 1)
            .read_to_end(&mut output)
            .map(|_| output);
        let _ = tx.send(result);
    });
    let deadline = Instant::now() + Duration::from_secs(5);
    let result = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) => (),
            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(error);
            }
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            return Err(invalid(format!("{label} prerequisite probe timed out")));
        }
        std::thread::sleep(Duration::from_millis(10));
    };
    if !result.success() {
        return Err(invalid(format!(
            "{label} executable failed its runtime probe"
        )));
    }
    let output = rx
        .recv_timeout(deadline.saturating_duration_since(Instant::now()))
        .map_err(|_| invalid(format!("{label} probe did not close its output")))??;
    if output.len() > limit {
        return Err(invalid(format!("{label} probe output exceeds bound")));
    }
    Ok(output)
}

/// Execute the interpreter probe rather than trusting a PATH entry (Windows Store aliases exist).
fn resolve_python(explicit: Option<&str>) -> io::Result<PathBuf> {
    let override_path = explicit
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("EMUCAP_PYTHON").map(PathBuf::from));
    let mut command = if let Some(path) = override_path {
        Command::new(path)
    } else if cfg!(windows) {
        let mut command = Command::new("py");
        command.arg("-3.12");
        command
    } else {
        Command::new("python3")
    };
    command.args(["-I", "-c", "import sys,struct,json; print(json.dumps([sys.version_info.major,sys.version_info.minor,struct.calcsize('P'),sys.executable]))"]);
    let output = probe_output(command, 16 * 1024, "Python")?;
    let (major, minor, pointer_size, executable): (u32, u32, usize, String) =
        serde_json::from_slice(&output)
            .map_err(|_| invalid("Python prerequisite probe is not a real Python runtime"))?;
    if major != 3 || minor < 12 || pointer_size != std::mem::size_of::<usize>() {
        return Err(invalid(
            "Azahar requires Python 3.12+ with the host architecture",
        ));
    }
    regular(Path::new(&executable).canonicalize()?)
}

/// Query native identity without loading a guest, before replacement can signal the old generation.
pub fn verify_compiled_profile(selected: &ResolvedEmulator) -> io::Result<()> {
    let mut command;
    if selected.profile.family == EmulatorFamily::AzaharLibretro {
        let mut host = Command::new(&selected.binary);
        host.arg("--host-info");
        let value: serde_json::Value =
            serde_json::from_slice(&probe_output(host, 16 * 1024, "Azahar supervisor")?)
                .map_err(|error| invalid(format!("invalid Azahar supervisor identity: {error}")))?;
        if value["schema"] != "emucap-azahar-host/v1"
            || value["bridge_api"] != 1
            || value["worker_protocol"] != 1
        {
            return Err(invalid("incompatible Azahar supervisor API"));
        }
        command = Command::new(
            selected
                .python
                .as_ref()
                .ok_or_else(|| invalid("Azahar interpreter missing"))?,
        );
        command.args(["-I","-c", "import ctypes,json,os,pathlib,sys; p=pathlib.Path(sys.argv[1]); d=os.add_dll_directory(str(p.parent)) if sys.platform=='win32' else None; c=ctypes.CDLL(str(p)); f=c.emucap_get_build_profile_json; f.restype=ctypes.c_char_p; f.argtypes=[]; print(json.dumps(json.loads(f())))"])
            .arg(selected.core.as_ref().ok_or_else(||invalid("Azahar core missing"))?);
    } else {
        command = Command::new(&selected.binary);
        command.arg("--emucap-build-profile");
    }
    let profile: BuildProfile =
        serde_json::from_slice(&probe_output(command, 64 * 1024, "native build identity")?)
            .map_err(|error| invalid(format!("native build identity query failed: {error}")))?;
    profile.validate().map_err(invalid)?;
    if profile != selected.profile {
        return Err(invalid(
            "compiled emulator profile differs from selected sidecar",
        ));
    }
    Ok(())
}

pub fn resolve_verified(
    root: &Path,
    system: &str,
    options: &EmulatorOptions,
) -> io::Result<ResolvedEmulator> {
    let selected = resolve(root, system, options)?;
    verify_compiled_profile(&selected)?;
    Ok(selected)
}

pub fn resolve(
    root: &Path,
    system: &str,
    options: &EmulatorOptions,
) -> io::Result<ResolvedEmulator> {
    let azahar = system == "3ds";
    if !azahar && !matches!(system, "switch" | "switch2") {
        return Err(invalid(
            "emulator selection is only supported for 3ds, switch and switch2",
        ));
    }
    if !azahar && (options.core.is_some() || options.python.is_some()) {
        return Err(invalid("core and python overrides apply only to Azahar"));
    }
    if azahar && options.config.is_some() {
        return Err(invalid(
            "Azahar uses locked libretro options, not an external SDL config",
        ));
    }
    let fork = options.fork.as_deref().unwrap_or(if azahar {
        "azahar"
    } else if system == "switch2" {
        "eden-nx2"
    } else {
        "eden"
    });
    let explicit_profile = options
        .profile
        .as_deref()
        .map(Path::new)
        .map(read_profile)
        .transpose()?;
    let ryujinx = fork == "ryubing"
        || explicit_profile
            .as_ref()
            .is_some_and(|profile| profile.family == EmulatorFamily::RyujinxFamily);
    let binary = if azahar {
        selected_path(
            options.binary.as_deref(),
            "EMUCAP_AZAHAR_HOST",
            root.join("target/release")
                .join(format!("emucap-azahar{}", std::env::consts::EXE_SUFFIX)),
        )
    } else if ryujinx {
        selected_path(
            options.binary.as_deref(),
            "EMUCAP_RYUJINX_BIN",
            root.join("adapters/ryujinx-family/build")
                .join(fork)
                .join("bin")
                .join(format!("Ryujinx{}", std::env::consts::EXE_SUFFIX)),
        )
    } else {
        selected_path(
            options.binary.as_deref(),
            "EMUCAP_EDEN_BIN",
            root.join("adapters/eden-family/build")
                .join(fork)
                .join("bin")
                .join(format!("eden-sdl{}", std::env::consts::EXE_SUFFIX)),
        )
    };
    let binary = regular(binary)
        .map_err(|error| invalid(format!("compatible emulator binary unavailable: {error}")))?;
    let core = if azahar {
        Some(regular(selected_path(
            options.core.as_deref(),
            "EMUCAP_AZAHAR_CORE",
            root.join("adapters/azahar/build")
                .join(format!("azahar_libretro{}", std::env::consts::DLL_SUFFIX)),
        ))?)
    } else {
        None
    };
    let profile_path = regular(
        options
            .profile
            .as_ref()
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                core.as_deref()
                    .unwrap_or(&binary)
                    .parent()
                    .unwrap()
                    .join("emucap-emulator-build.json")
            }),
    )
    .map_err(|error| invalid(format!("compatible-build profile required: {error}")))?;
    let profile = read_profile(&profile_path)?;
    if profile.fork != fork
        || if azahar {
            profile.family != EmulatorFamily::AzaharLibretro
        } else {
            !matches!(
                profile.family,
                EmulatorFamily::EdenFamily | EmulatorFamily::RyujinxFamily
            )
        }
    {
        return Err(invalid(
            "selected emulator fork/family does not match build profile",
        ));
    }
    let renderer =
        options
            .renderer
            .as_deref()
            .unwrap_or(if azahar { "software" } else { "vulkan" });
    profile
        .validate_selection(system, renderer)
        .map_err(invalid)?;
    let os = if cfg!(target_os = "macos") {
        "darwin"
    } else {
        std::env::consts::OS
    };
    if !profile.target.starts_with(std::env::consts::ARCH)
        || !profile.target.contains(os)
        || profile
            .cpu_features
            .iter()
            .any(|feature| !cpu_feature_available(feature))
    {
        return Err(invalid(
            "emulator build requires an incompatible host architecture or CPU feature",
        ));
    }
    let config = options.config.as_deref().map(regular).transpose()?;
    let python = if azahar {
        Some(resolve_python(options.python.as_deref())?)
    } else {
        None
    };
    let worker = if azahar {
        Some(regular(root.join("adapters/azahar/bridge.py"))?)
    } else {
        None
    };
    Ok(ResolvedEmulator {
        binary,
        core,
        python,
        worker,
        profile_path,
        profile,
        config,
        system: system.into(),
        renderer: renderer.into(),
    })
}

#[allow(clippy::too_many_arguments)]
pub fn process_spec(
    selected: &ResolvedEmulator,
    content: &str,
    user_root: &Path,
    log: &Path,
    receipt: &Path,
    port: u16,
    token: &str,
    runtime: RuntimeEnv<'_>,
    display: bool,
    name: Option<&str>,
) -> LaunchSpec {
    let mut spec = LaunchSpec::new(&selected.binary, log)
        .runtime_env(Some(runtime))
        .env("EMUCAP_PORT", port.to_string())
        .env("EMUCAP_SESSION_TOKEN", token)
        .env("EMUCAP_SYSTEM", &selected.system)
        .env("EMUCAP_RENDERER", &selected.renderer)
        .env("EMUCAP_USER_ROOT", user_root.to_string_lossy().to_string())
        .env(
            "EMUCAP_BUILD_PROFILE",
            user_root
                .join("emucap-emulator-build.json")
                .to_string_lossy()
                .to_string(),
        )
        .env("EMUCAP_DISPLAY", if display { "1" } else { "0" });
    if let Some(name) = name {
        spec = spec.env("EMUCAP_NAME", name);
    }
    if selected.profile.family == EmulatorFamily::AzaharLibretro {
        spec.args([
            port.to_string(),
            selected.python.as_ref().unwrap().display().to_string(),
            selected.worker.as_ref().unwrap().display().to_string(),
            selected.core.as_ref().unwrap().display().to_string(),
            content.into(),
            user_root.display().to_string(),
            user_root
                .join("emucap-emulator-build.json")
                .display()
                .to_string(),
            receipt.display().to_string(),
        ])
    } else if selected.profile.family == EmulatorFamily::RyujinxFamily {
        // LoadCart accepts the ExeFS directory; admission/readback still bind its main entry.
        let content = Path::new(content);
        let input = if content.file_name().is_some_and(|name| name == "main") {
            content.parent().unwrap_or(content)
        } else {
            content
        };
        spec.args([
            "--no-gui".into(),
            "--root-data-dir".into(),
            user_root.display().to_string(),
            "--disable-main-input-config".into(),
            "--disable-docked-mode".into(),
            "--graphics-backend".into(),
            if selected.renderer == "opengl" {
                "OpenGl"
            } else {
                "Vulkan"
            }
            .into(),
            input.display().to_string(),
        ])
    } else {
        spec.args([
            "--config".into(),
            user_root.join("config.ini").display().to_string(),
            content.into(),
        ])
    }
}

#[derive(Debug)]
pub struct StartedEmulator {
    pub emulator_pid: u32,
    pub bridge_pid: Option<u32>,
    pub user_root: PathBuf,
}

fn stage_config(selected: &ResolvedEmulator, user_root: &Path) -> io::Result<()> {
    if let Some(config) = &selected.config {
        let mut input = crate::path_safety::open_regular_file_no_follow(config)?;
        if input.metadata()?.len() > 1024 * 1024 {
            return Err(invalid("emulator config exceeds 1 MiB"));
        }
        let mut bytes = Vec::new();
        input
            .by_ref()
            .take(1024 * 1024 + 1)
            .read_to_end(&mut bytes)?;
        if bytes.len() > 1024 * 1024 {
            return Err(invalid("emulator config grew beyond bound"));
        }
        let filename = if selected.profile.family == EmulatorFamily::RyujinxFamily {
            "emucap-config.json"
        } else {
            "config.ini"
        };
        crate::path_safety::atomic_write_file(&user_root.join(filename), &bytes)?;
    }
    Ok(())
}

pub fn launch(
    selected: &ResolvedEmulator,
    content: &str,
    port: u16,
    token: &str,
    runtime: RuntimeEnv<'_>,
    display: bool,
    name: Option<&str>,
) -> io::Result<StartedEmulator> {
    let generation = super::runtime_generation_dir(port, runtime)?;
    let user_root = super::emu_generation_dir(
        match selected.profile.family {
            EmulatorFamily::AzaharLibretro => "azahar",
            EmulatorFamily::EdenFamily => "eden-family",
            EmulatorFamily::RyujinxFamily => "ryujinx-family",
        },
        port,
        Some(runtime),
    )?;
    let profile = serde_json::to_vec(&selected.profile).map_err(io::Error::other)?;
    crate::path_safety::atomic_write_file(&user_root.join("emucap-emulator-build.json"), &profile)?;
    stage_config(selected, &user_root)?;
    let receipt = generation.join("azahar-startup.json");
    let spec = process_spec(
        selected,
        content,
        &user_root,
        &generation.join("emulator.log"),
        &receipt,
        port,
        token,
        runtime,
        display,
        name,
    );
    let pid = super::spawn_detached(&spec)?;
    if selected.profile.family != EmulatorFamily::AzaharLibretro {
        return Ok(StartedEmulator {
            emulator_pid: pid,
            bridge_pid: None,
            user_root,
        });
    }
    let host = crate::live::runtime::capture_process(pid);
    let deadline = Instant::now() + Duration::from_secs(30);
    loop {
        let result = (|| -> io::Result<crate::live::runtime::ProcessIdentity> {
            let file = crate::path_safety::open_regular_file_no_follow(&receipt)?;
            let mut bytes = Vec::new();
            file.take(16 * 1024 + 1).read_to_end(&mut bytes)?;
            if bytes.len() > 16 * 1024 {
                return Err(invalid("Azahar startup receipt exceeds bound"));
            }
            let value: serde_json::Value =
                serde_json::from_slice(&bytes).map_err(io::Error::other)?;
            let receipt_host: crate::live::runtime::ProcessIdentity =
                serde_json::from_value(value["host"].clone()).map_err(io::Error::other)?;
            let worker: crate::live::runtime::ProcessIdentity =
                serde_json::from_value(value["worker"].clone()).map_err(io::Error::other)?;
            if value["schema_version"] != 1
                || value["launch_id"] != runtime.launch_id
                || receipt_host != host
                || worker.pid == host.pid
                || worker.start_identity.is_none()
                || crate::live::runtime::process_state(&worker)
                    != crate::live::runtime::ProcessState::Alive
            {
                return Err(invalid(
                    "Azahar startup receipt has invalid generation/process ownership",
                ));
            }
            Ok(worker)
        })();
        match result {
            Ok(worker) => {
                return Ok(StartedEmulator {
                    emulator_pid: worker.pid,
                    bridge_pid: Some(pid),
                    user_root,
                })
            }
            Err(error) if error.kind() != io::ErrorKind::NotFound => {
                let _ = super::terminate_detached(pid);
                return Err(error);
            }
            Err(_) => (),
        }
        if Instant::now() >= deadline
            || crate::live::runtime::process_state(&host)
                != crate::live::runtime::ProcessState::Alive
        {
            let _ = super::terminate_detached(pid);
            return Err(invalid(
                "Azahar supervisor did not publish owned worker identity before deadline",
            ));
        }
        std::thread::sleep(Duration::from_millis(20));
    }
}

#[cfg(test)]
#[path = "emulator_family_tests.rs"]
mod tests;

use super::*;
use crate::emulator_profile::{maintained_source, BUILD_PROFILE_SCHEMA};

#[test]
fn executable_probe_rejects_output_above_its_byte_budget() {
    let python = resolve_python(None).unwrap();
    let mut command = Command::new(python);
    command.args(["-I", "-c", "print('x' * 32768)"]);
    assert!(probe_output(command, 16 * 1024, "bounded-output-test").is_err());
}

#[test]
fn executable_probe_timeout_reaps_the_exact_child() {
    let python = resolve_python(None).unwrap();
    let root = tempfile::tempdir().unwrap();
    let marker = root.path().join("probe-pid");
    let worker_marker = marker.clone();
    let started = Instant::now();
    let worker = std::thread::spawn(move || {
        let mut command = Command::new(python);
        command.args(["-I", "-c", "import os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"])
            .arg(worker_marker);
        probe_output(command, 1024, "bounded-time-test")
    });
    while !marker.is_file() && started.elapsed() < Duration::from_secs(4) {
        std::thread::sleep(Duration::from_millis(10));
    }
    let pid: u32 = std::fs::read_to_string(marker).unwrap().parse().unwrap();
    let identity = crate::live::runtime::capture_process(pid);
    assert!(identity.start_identity.is_some());
    let error = worker.join().unwrap().unwrap_err();
    assert!(error.to_string().contains("probe timed out"));
    assert!(started.elapsed() < Duration::from_secs(8));
    assert_eq!(
        crate::live::runtime::process_state(&identity),
        crate::live::runtime::ProcessState::Exited
    );
}

#[cfg(unix)]
#[test]
fn python_probe_accepts_a_real_interpreter_symlink() {
    let output = Command::new("python3")
        .args([
            "-c",
            "import os,sys; print(os.path.realpath(sys.executable))",
        ])
        .output()
        .expect("Python 3.12+ is required for emulator-family tests");
    assert!(output.status.success());
    let executable = PathBuf::from(String::from_utf8(output.stdout).unwrap().trim());
    let root = tempfile::tempdir().unwrap();
    let alias = root.path().join("python alias");
    std::os::unix::fs::symlink(&executable, &alias).unwrap();
    assert_eq!(
        resolve_python(Some(alias.to_str().unwrap())).unwrap(),
        executable.canonicalize().unwrap()
    );
}

fn native() -> ResolvedEmulator {
    let pin = maintained_source("eglantine").unwrap();
    ResolvedEmulator {
        binary: PathBuf::from("/emulator path/eden-sdl"),
        core: None,
        python: None,
        worker: None,
        profile_path: PathBuf::from("/profile.json"),
        config: None,
        system: "switch2".into(),
        renderer: "vulkan".into(),
        profile: BuildProfile {
            schema: BUILD_PROFILE_SCHEMA.into(),
            family: EmulatorFamily::EdenFamily,
            fork: pin.fork.into(),
            repository: pin.repository.into(),
            revision: pin.revision.into(),
            patch_sha256: "ab".repeat(32),
            bridge_api: 1,
            systems: vec!["switch2".into()],
            renderers: vec!["vulkan".into()],
            cpu_features: vec![],
            target: format!(
                "{}-{}",
                std::env::consts::ARCH,
                if cfg!(target_os = "macos") {
                    "darwin"
                } else {
                    std::env::consts::OS
                }
            ),
        },
    }
}

#[test]
fn native_spec_keeps_graphics_and_isolates_paths_with_spaces() {
    let selected = native();
    let runtime = RuntimeEnv {
        launch_id: "launch-test",
        adapter_failure_path: Path::new("/runtime/adapter-failure.json"),
    };
    let spec = process_spec(
        &selected,
        "/content path/exefs/main",
        Path::new("/managed root"),
        Path::new("/log"),
        Path::new("/receipt"),
        5555,
        "private-key",
        runtime,
        false,
        Some("guest"),
    );
    assert_eq!(
        spec.args,
        vec![
            "--config".to_string(),
            Path::new("/managed root")
                .join("config.ini")
                .display()
                .to_string(),
            "/content path/exefs/main".to_string()
        ]
    );
    assert!(spec
        .env
        .iter()
        .any(|(key, value)| key == "EMUCAP_USER_ROOT" && value == "/managed root"));
    assert!(spec
        .env
        .iter()
        .any(|(key, value)| key == "EMUCAP_DISPLAY" && value == "0"));
    assert!(!spec.args.iter().any(|arg| arg == "--null-render"));
}

#[test]
fn unpatched_stock_binary_is_rejected_before_launch() {
    let root = tempfile::tempdir().unwrap();
    let binary = root.path().join("eden.exe");
    std::fs::write(&binary, b"not-a-patched-build").unwrap();
    let options = EmulatorOptions {
        binary: Some(binary.display().to_string()),
        ..Default::default()
    };
    assert!(resolve(root.path(), "switch", &options)
        .unwrap_err()
        .to_string()
        .contains("profile"));
}

#[test]
fn native_preflight_binds_explicit_fork_system_renderer_and_host() {
    let root = tempfile::tempdir().unwrap();
    let binary = root.path().join("eden.exe");
    let profile = root.path().join("emucap-emulator-build.json");
    std::fs::write(&binary, b"binary").unwrap();
    std::fs::write(&profile, serde_json::to_vec(&native().profile).unwrap()).unwrap();
    let mut options = EmulatorOptions {
        binary: Some(binary.display().to_string()),
        fork: Some("eglantine".into()),
        ..Default::default()
    };
    assert!(resolve(root.path(), "switch2", &options).is_ok());
    assert!(resolve(root.path(), "switch", &options).is_err());
    options.renderer = Some("null".into());
    assert!(resolve(root.path(), "switch2", &options).is_err());
}

fn ryubing() -> ResolvedEmulator {
    let mut selected = native();
    selected.profile.family = EmulatorFamily::RyujinxFamily;
    selected.profile.fork = "ryubing".into();
    selected.profile.repository = "https://git.ryujinx.app/projects/Ryubing.git".into();
    selected.profile.revision = "a61a42681119bf15fe8f3297677ae48bda83e70f".into();
    selected.profile.systems = vec!["switch".into()];
    selected.profile.renderers = vec!["vulkan".into(), "opengl".into()];
    selected.system = "switch".into();
    selected
}

#[test]
fn ryubing_preflight_accepts_maintained_and_explicit_custom_profiles() {
    let root = tempfile::tempdir().unwrap();
    let binary = root.path().join("Ryujinx.exe");
    let sidecar = root.path().join("emucap-emulator-build.json");
    std::fs::write(&binary, b"synthetic selection fixture").unwrap();
    let mut profile = ryubing().profile;
    std::fs::write(&sidecar, serde_json::to_vec(&profile).unwrap()).unwrap();
    let mut options = EmulatorOptions {
        fork: Some("ryubing".into()),
        binary: Some(binary.display().to_string()),
        ..Default::default()
    };
    assert_eq!(
        resolve(root.path(), "switch", &options)
            .unwrap()
            .profile
            .family,
        EmulatorFamily::RyujinxFamily
    );
    assert!(resolve(root.path(), "switch2", &options).is_err());
    profile.fork = "custom-ryujinx".into();
    profile.repository = "https://example.test/custom.git".into();
    profile.revision = "cd".repeat(20);
    options.fork = Some(profile.fork.clone());
    std::fs::write(&sidecar, serde_json::to_vec(&profile).unwrap()).unwrap();
    assert!(resolve(root.path(), "switch", &options).is_ok());
    profile.systems.push("switch2".into());
    std::fs::write(&sidecar, serde_json::to_vec(&profile).unwrap()).unwrap();
    assert!(resolve(root.path(), "switch2", &options).is_err());
}

#[test]
fn ryubing_spec_uses_native_cli_and_exefs_directory_without_config_flag() {
    let mut selected = ryubing();
    selected.renderer = "opengl".into();
    let runtime = RuntimeEnv {
        launch_id: "test",
        adapter_failure_path: Path::new("/failure"),
    };
    let spec = process_spec(
        &selected,
        "/content path/exefs/main",
        Path::new("/managed root"),
        Path::new("/log"),
        Path::new("/receipt"),
        5555,
        "private",
        runtime,
        false,
        None,
    );
    assert_eq!(
        spec.args,
        vec![
            "--no-gui",
            "--root-data-dir",
            "/managed root",
            "--disable-main-input-config",
            "--disable-docked-mode",
            "--graphics-backend",
            "OpenGl",
            "/content path/exefs"
        ]
    );
    selected.renderer = "vulkan".into();
    let spec = process_spec(
        &selected,
        "/content path/guest.nro",
        Path::new("/managed root"),
        Path::new("/log"),
        Path::new("/receipt"),
        5555,
        "private",
        runtime,
        false,
        None,
    );
    assert_eq!(spec.args.last().unwrap(), "/content path/guest.nro");
    assert!(spec.args.iter().any(|arg| arg == "Vulkan"));
}

#[test]
fn ryubing_default_binary_and_explicit_override_are_admitted() {
    let root = tempfile::tempdir().unwrap();
    let default = root
        .path()
        .join("adapters/ryujinx-family/build/ryubing/bin")
        .join(format!("Ryujinx{}", std::env::consts::EXE_SUFFIX));
    std::fs::create_dir_all(default.parent().unwrap()).unwrap();
    std::fs::write(&default, b"synthetic default binary").unwrap();
    std::fs::write(
        default.parent().unwrap().join("emucap-emulator-build.json"),
        serde_json::to_vec(&ryubing().profile).unwrap(),
    )
    .unwrap();
    let mut options = EmulatorOptions {
        fork: Some("ryubing".into()),
        ..Default::default()
    };
    // Explicit selection is independent of any machine-local environment override.
    options.binary = Some(default.display().to_string());
    assert_eq!(
        resolve(root.path(), "switch", &options).unwrap().binary,
        default.canonicalize().unwrap()
    );
    if std::env::var_os("EMUCAP_RYUJINX_BIN").is_none() {
        options.binary = None;
        assert_eq!(
            resolve(root.path(), "switch", &options).unwrap().binary,
            default.canonicalize().unwrap()
        );
    }
}

#[test]
fn ryubing_config_staging_copies_only_explicit_json_and_preserves_eden_ini() {
    let root = tempfile::tempdir().unwrap();
    let generation = root.path().join("generation");
    std::fs::create_dir(&generation).unwrap();
    let source = root.path().join("selected-config.json");
    let bytes = br#"{"preferred_gpu_vendor":"AMD"}"#;
    std::fs::write(&source, bytes).unwrap();
    let mut selected = ryubing();
    selected.config = Some(source.clone());
    stage_config(&selected, &generation).unwrap();
    assert_eq!(
        std::fs::read(generation.join("emucap-config.json")).unwrap(),
        bytes
    );
    assert!(!generation.join("config.ini").exists());
    assert_eq!(std::fs::read(&source).unwrap(), bytes);
    let mut eden = native();
    eden.config = Some(source.clone());
    stage_config(&eden, &generation).unwrap();
    assert_eq!(std::fs::read(generation.join("config.ini")).unwrap(), bytes);
    std::fs::write(source, vec![0; 1024 * 1024 + 1]).unwrap();
    assert!(stage_config(&selected, &generation).is_err());
    assert_eq!(
        std::fs::read(generation.join("emucap-config.json")).unwrap(),
        bytes
    );
}

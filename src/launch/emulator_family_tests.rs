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

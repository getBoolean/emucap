use emucap::emulator_profile::{
    maintained_source, BuildProfile, EmulatorFamily, BUILD_PROFILE_SCHEMA,
};
use emucap::launch::emulator_family::{verify_compiled_profile, ResolvedEmulator};
use std::path::PathBuf;
use std::process::Command;

fn selection(family: EmulatorFamily) -> ResolvedEmulator {
    let pin = maintained_source(if family == EmulatorFamily::AzaharLibretro {
        "azahar"
    } else {
        "eden"
    })
    .unwrap();
    ResolvedEmulator {
        binary: PathBuf::from(env!("CARGO_BIN_EXE_emucap-azahar")),
        core: None,
        python: None,
        worker: None,
        profile_path: PathBuf::new(),
        config: None,
        system: pin.systems[0].into(),
        renderer: if family == EmulatorFamily::AzaharLibretro {
            "software"
        } else {
            "vulkan"
        }
        .into(),
        profile: BuildProfile {
            schema: BUILD_PROFILE_SCHEMA.into(),
            family,
            fork: pin.fork.into(),
            repository: pin.repository.into(),
            revision: pin.revision.into(),
            patch_sha256: "ab".repeat(32),
            bridge_api: 1,
            systems: vec![pin.systems[0].into()],
            renderers: vec![if family == EmulatorFamily::AzaharLibretro {
                "software"
            } else {
                "vulkan"
            }
            .into()],
            cpu_features: vec![],
            target: "test-host".into(),
        },
    }
}

#[test]
fn supervisor_probe_has_an_explicit_versioned_api_without_loading_a_core() {
    let output = Command::new(env!("CARGO_BIN_EXE_emucap-azahar"))
        .arg("--host-info")
        .output()
        .unwrap();
    assert!(output.status.success());
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["schema"], "emucap-azahar-host/v1");
    assert_eq!(value["bridge_api"], 1);
    assert_eq!(value["worker_protocol"], 1);
}

#[test]
fn a_valid_sidecar_does_not_admit_an_unrelated_native_executable() {
    let selected = selection(EmulatorFamily::EdenFamily);
    selected.profile.validate().unwrap();
    let error = verify_compiled_profile(&selected).unwrap_err();
    assert!(error.to_string().contains("native build identity"));
}

#[test]
fn core_probe_rejects_invalid_library_without_creating_a_guest_workspace() {
    let root = tempfile::tempdir().unwrap();
    let mut python = if cfg!(windows) {
        let mut command = Command::new("py");
        command.arg("-3.12");
        command
    } else {
        Command::new("python3")
    };
    let output = python
        .args([
            "-c",
            "import os,sys; print(os.path.realpath(sys.executable))",
        ])
        .output()
        .unwrap();
    assert!(output.status.success());
    let mut selected = selection(EmulatorFamily::AzaharLibretro);
    selected.python = Some(PathBuf::from(
        String::from_utf8(output.stdout).unwrap().trim(),
    ));
    let core = root.path().join("unrelated-library");
    std::fs::write(&core, b"not a shared library").unwrap();
    selected.core = Some(core);
    let error = verify_compiled_profile(&selected).unwrap_err();
    assert!(error.to_string().contains("native build identity"));
    assert!(!root.path().join("Azahar").exists());
}

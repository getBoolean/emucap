use super::*;
use serde_json::json;

fn eden() -> BuildProfile {
    BuildProfile {
        schema: BUILD_PROFILE_SCHEMA.into(),
        family: EmulatorFamily::EdenFamily,
        fork: "eden-nx2".into(),
        repository: maintained_source("eden-nx2").unwrap().repository.into(),
        revision: maintained_source("eden-nx2").unwrap().revision.into(),
        patch_sha256: "ab".repeat(32),
        bridge_api: BRIDGE_API_VERSION,
        systems: vec!["switch".into(), "switch2".into()],
        renderers: vec!["vulkan".into()],
        cpu_features: vec![],
        target: "x86_64-pc-windows-msvc".into(),
    }
}

#[test]
fn experimental_fork_pin_uses_its_real_branch() {
    let pin = maintained_source("eden-nx2").unwrap();
    assert_eq!(pin.reference, "eden-nx2");
    assert_eq!(pin.revision, "50fa86bbbc403ad565eb44fcc281f16f77c69e15");
    assert_eq!(maintained_source("eden").unwrap().systems, &["switch"]);
    let eglantine = maintained_source("eglantine").unwrap();
    assert_eq!(
        eglantine.repository,
        "https://github.com/Djihads80/Eglantine.git"
    );
    assert_eq!(eglantine.reference, "nx2");
    assert_eq!(
        eglantine.revision,
        "c54bc2289bfffda7fa3cc4c3a8cf522d84a10fd4"
    );
    assert!(maintained_source("unknown-fork").is_none());
}

#[test]
fn profiles_admit_only_explicit_build_system_and_renderer() {
    let mut profile = eden();
    assert!(profile.validate_selection("switch2", "vulkan").is_ok());
    assert!(profile.validate_selection("3ds", "vulkan").is_err());
    assert!(profile.validate_selection("switch2", "null").is_err());
    profile.bridge_api += 1;
    assert!(profile.validate().is_err());
    profile = eden();
    profile.patch_sha256 = String::new();
    assert!(profile.validate().is_err());
    profile = eden();
    profile.systems.push("switch".into());
    assert!(profile.validate().is_err());
}

#[test]
fn custom_forks_require_explicit_provenance_but_no_copied_adapter() {
    let mut profile = eden();
    profile.fork = "my-fork".into();
    profile.repository = "https://example.test/my-fork".into();
    profile.revision = "cd".repeat(20);
    assert!(profile.validate().is_ok());
    assert_eq!(profile.family.adapter(), "eden-family-native");
    profile.family = EmulatorFamily::AzaharLibretro;
    assert!(profile.validate().is_err());
}

#[test]
fn live_hello_must_match_selected_metadata_and_runtime_selection() {
    let profile = eden();
    let mut hello = json!({
        "protocol_version":1,"adapter":"eden-family-native","system":"switch2",
        "renderer":"vulkan","host_build":profile,
        "methods":["hello","status","screenshot","set_input"]
    });
    assert!(profile.validate_hello(&hello).is_ok());
    hello["host_build"]["revision"] = json!("ee".repeat(20));
    assert!(profile.validate_hello(&hello).is_err());
    hello["host_build"] = json!(profile);
    hello["session_token"] = json!("must-not-be-public");
    assert!(profile.validate_hello(&hello).is_err());
    hello.as_object_mut().unwrap().remove("session_token");
    hello["renderer"] = json!("opengl");
    assert!(profile.validate_hello(&hello).is_err());
}

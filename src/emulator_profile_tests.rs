use super::*;
use serde_json::json;

#[test]
fn every_builder_descriptor_is_admitted_without_a_parallel_pin_table() {
    let pins = maintained_sources();
    let mut forks = std::collections::BTreeSet::new();
    assert_eq!(pins.len(), 7);
    for pin in pins {
        assert!(forks.insert(&pin.fork));
        let profile = BuildProfile {
            schema: BUILD_PROFILE_SCHEMA.into(),
            family: pin.family,
            fork: pin.fork.clone(),
            repository: pin.repository.clone(),
            revision: pin.revision.clone(),
            systems: pin.systems.clone(),
            renderers: vec![if matches!(
                pin.family,
                EmulatorFamily::AzaharLibretro | EmulatorFamily::SoftwareLibretro
            ) {
                "software".into()
            } else {
                "vulkan".into()
            }],
            patch_sha256: "ab".repeat(32),
            bridge_api: BRIDGE_API_VERSION,
            cpu_features: vec![],
            target: "test-host".into(),
        };
        assert!(
            profile.validate().is_ok(),
            "{} descriptor rejected",
            pin.fork
        );
    }
}

#[test]
fn software_cores_are_pinned_and_cannot_claim_other_systems() {
    for (fork, system, wrong) in [("mgba", "gba", "nds"), ("melonds", "nds", "gba")] {
        let pin = maintained_source(fork).unwrap();
        let mut profile = eden();
        profile.family = EmulatorFamily::SoftwareLibretro;
        profile.fork = fork.into();
        profile.repository = pin.repository.clone();
        profile.revision = pin.revision.clone();
        profile.systems = vec![system.into()];
        profile.renderers = vec!["software".into()];
        assert!(profile.validate_selection(system, "software").is_ok());
        assert!(profile.validate_selection(system, "opengl").is_err());
        profile.systems = vec![wrong.into()];
        assert!(profile.validate().is_err());
    }
}

fn eden() -> BuildProfile {
    BuildProfile {
        schema: BUILD_PROFILE_SCHEMA.into(),
        family: EmulatorFamily::EdenFamily,
        fork: "eden-nx2".into(),
        repository: maintained_source("eden-nx2").unwrap().repository.clone(),
        revision: maintained_source("eden-nx2").unwrap().revision.clone(),
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

#[test]
fn ryubing_profile_is_distinct_pinned_and_switch_one_only() {
    let pin = maintained_source("ryubing").unwrap();
    assert_eq!(pin.family, EmulatorFamily::RyujinxFamily);
    assert_eq!(
        pin.repository,
        "https://git.ryujinx.app/projects/Ryubing.git"
    );
    assert_eq!(pin.reference, "master");
    assert_eq!(pin.revision, "a61a42681119bf15fe8f3297677ae48bda83e70f");
    let mut profile = eden();
    profile.family = EmulatorFamily::RyujinxFamily;
    profile.fork = pin.fork.clone();
    profile.repository = pin.repository.clone();
    profile.revision = pin.revision.clone();
    profile.systems = vec!["switch".into()];
    assert!(profile.validate_selection("switch", "vulkan").is_ok());
    assert_eq!(profile.family.adapter(), "ryujinx-family-native");
    let mut hello = json!({"protocol_version":1,"adapter":"ryujinx-family-native",
        "system":"switch","renderer":"vulkan","host_build":profile});
    assert!(profile.validate_hello(&hello).is_ok());
    hello["adapter"] = json!("eden-family-native");
    assert!(profile.validate_hello(&hello).is_err());
    profile.fork = "custom-ryujinx".into();
    profile.repository = "https://example.test/custom-ryujinx.git".into();
    profile.revision = "cd".repeat(20);
    assert!(profile.validate().is_ok());
    profile.systems.push("switch2".into());
    assert!(profile.validate().is_err());
}

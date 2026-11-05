use super::*;
use emucap::launch::emulator_family::{self as family, EmulatorOptions, ResolvedEmulator};

pub(super) fn is_family(adapter: &str) -> bool {
    matches!(adapter, "azahar" | "eden_family" | "software_libretro")
}

pub(super) fn precondition(
    root: &Path,
    system: &str,
    options: Option<&EmulatorOptions>,
) -> serde_json::Value {
    match family::resolve_verified(root, system, options.unwrap_or(&EmulatorOptions::default())) {
        Ok(selected) => serde_json::json!({
            "available":true,"path":selected.binary.display().to_string(),
            "profile":selected.profile,"renderer":selected.renderer,
            "core":selected.runtime.core().map(|path|path.display().to_string()),
            "python":selected.runtime.python().map(|path|path.display().to_string()),
            "qualification":"experimental; inspect per-build live evidence",
        }),
        Err(error) => {
            serde_json::json!({"available":false,"kind":"compatible-emulator-build-required",
            "error":error.to_string(),"system":system,
            "guide":if system=="3ds" {"adapters/azahar/README.md"}
                else if matches!(system, "nds" | "gba") {"adapters/libretro/README.md"}
                else if options.is_some_and(|options| options.fork.as_deref() == Some("ryubing")) {"adapters/ryujinx-family/README.md"}
                else {"adapters/eden-family/README.md"}})
        }
    }
}

pub(super) fn start(
    selected: &ResolvedEmulator,
    port: u16,
    token: Option<&str>,
    runtime: RuntimeEnv<'_>,
    args: &LaunchArgs,
) -> serde_json::Value {
    let Some(token) = token else {
        return serde_json::json!({"launched":false,"error":"producer credential missing"});
    };
    match family::launch(
        selected,
        &args.content_path,
        port,
        token,
        runtime,
        args.display.unwrap_or(false),
        args.name.as_deref(),
    ) {
        Ok(started) => serde_json::json!({"launched":true,"pid":started.emulator_pid,
            "bridge_pid":started.bridge_pid,"runtime_content":args.content_path,
            "emulator_profile":selected.profile,"renderer":selected.renderer,
            "managed_user_root":started.user_root.display().to_string()}),
        Err(error) => {
            serde_json::json!({"launched":false,"reason":"emulator-family launch failed","error":error.to_string()})
        }
    }
}

pub(super) fn runtime_identity_error(
    selected: &ResolvedEmulator,
    status: &serde_json::Value,
    capabilities: &emucap::live::link::Capabilities,
    expected_root: &str,
) -> Result<(), String> {
    let identity = &capabilities.identity;
    let hello = serde_json::json!({"protocol_version":capabilities.protocol_version,
        "adapter":identity.adapter,"system":identity.system,"host_build":identity.host_build,
        "renderer":status.get("renderer")});
    selected.profile.validate_hello(&hello)?;
    if hello["system"] != selected.system || hello["renderer"] != selected.renderer {
        return Err("native runtime selection differs from admitted system/renderer".into());
    }
    let root = status
        .get("managed_user_root")
        .and_then(serde_json::Value::as_str)
        .ok_or("native runtime did not report its effective managed user root")?;
    if !emucap::content_identity::same_content_path(expected_root, root) {
        return Err("native runtime user root differs from the managed generation".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ryubing_native_readiness_requires_its_own_adapter_and_managed_root() {
        let root = tempfile::tempdir().unwrap();
        let pin = emucap::emulator_profile::maintained_source("ryubing").unwrap();
        let profile = serde_json::from_value(serde_json::json!({
            "schema":"emucap-emulator-build/v1", "family":"ryujinx-family",
            "fork":pin.fork,"repository":pin.repository,"revision":pin.revision,
            "patch_sha256":"ab".repeat(32),"bridge_api":1,"systems":["switch"],
            "renderers":["vulkan"],"cpu_features":[],"target":"x86_64-windows"
        }))
        .unwrap();
        let selected = ResolvedEmulator {
            binary: root.path().join("Ryujinx.exe"),
            runtime: family::ResolvedRuntime::Native,
            profile_path: root.path().join("profile.json"),
            config: None,
            system: "switch".into(),
            renderer: "vulkan".into(),
            profile,
        };
        let hello = serde_json::json!({"adapter":"ryujinx-family-native","system":"switch",
            "host_build":selected.profile});
        let mut capabilities = emucap::live::link::Capabilities::empty();
        capabilities.protocol_version = 1;
        capabilities.identity = emucap::live::link::EmulatorIdentity::from_hello(&hello);
        let expected = root.path().display().to_string();
        let status = serde_json::json!({"renderer":"vulkan","managed_user_root":expected});
        assert!(runtime_identity_error(&selected, &status, &capabilities, &expected).is_ok());
        assert!(runtime_identity_error(&selected, &status, &capabilities, "/other-root").is_err());
        capabilities.identity.adapter = Some("eden-family-native".into());
        assert!(runtime_identity_error(&selected, &status, &capabilities, &expected).is_err());
    }

    #[test]
    fn native_readiness_rejects_root_renderer_and_compiled_profile_mismatch() {
        let root = tempfile::tempdir().unwrap();
        let pin = emucap::emulator_profile::maintained_source("eglantine").unwrap();
        let profile: emucap::emulator_profile::BuildProfile = serde_json::from_value(
            serde_json::json!({"schema":"emucap-emulator-build/v1","family":"eden-family",
                "fork":pin.fork,"repository":pin.repository,"revision":pin.revision,
                "patch_sha256":"ab".repeat(32),"bridge_api":1,"systems":["switch","switch2"],
                "renderers":["vulkan","opengl"],"cpu_features":[],"target":"x86_64-windows"}),
        )
        .unwrap();
        let selected = ResolvedEmulator {
            binary: root.path().join("eden-sdl"),
            runtime: family::ResolvedRuntime::Native,
            profile_path: root.path().join("profile.json"),
            config: None,
            system: "switch2".into(),
            renderer: "vulkan".into(),
            profile,
        };
        let hello = serde_json::json!({"adapter":"eden-family-native","system":"switch2",
            "host_build":selected.profile});
        let mut capabilities = emucap::live::link::Capabilities::empty();
        capabilities.protocol_version = 1;
        capabilities.identity = emucap::live::link::EmulatorIdentity::from_hello(&hello);
        let expected = root.path().display().to_string();
        let status = serde_json::json!({"renderer":"vulkan","managed_user_root":expected});
        assert!(runtime_identity_error(&selected, &status, &capabilities, &expected).is_ok());
        for invalid in [
            serde_json::json!({"renderer":"vulkan"}),
            serde_json::json!({"renderer":"vulkan","managed_user_root":"/another-user-profile"}),
            serde_json::json!({"renderer":"opengl","managed_user_root":expected}),
        ] {
            assert!(runtime_identity_error(&selected, &invalid, &capabilities, &expected).is_err());
        }
        capabilities.identity.host_build.as_mut().unwrap()["patch_sha256"] =
            serde_json::json!("cd".repeat(32));
        assert!(runtime_identity_error(&selected, &status, &capabilities, &expected).is_err());
    }
}

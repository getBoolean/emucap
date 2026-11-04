//! Explicit source/build provenance for supervised and source-patched emulator families.
//! A profile admits a build; authentication and live capability validation remain separate.
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const BUILD_PROFILE_SCHEMA: &str = "emucap-emulator-build/v1";
pub const BRIDGE_API_VERSION: u32 = 1;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EmulatorFamily {
    AzaharLibretro,
    EdenFamily,
}

impl EmulatorFamily {
    pub fn adapter(self) -> &'static str {
        match self {
            Self::AzaharLibretro => "azahar-libretro",
            Self::EdenFamily => "eden-family-native",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BuildProfile {
    pub schema: String,
    pub family: EmulatorFamily,
    pub fork: String,
    pub repository: String,
    pub revision: String,
    pub patch_sha256: String,
    pub bridge_api: u32,
    pub systems: Vec<String>,
    pub renderers: Vec<String>,
    pub cpu_features: Vec<String>,
    pub target: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SourcePin {
    pub family: EmulatorFamily,
    pub fork: &'static str,
    pub repository: &'static str,
    pub reference: &'static str,
    pub revision: &'static str,
    pub systems: &'static [&'static str],
}

pub const MAINTAINED_SOURCES: &[SourcePin] = &[
    SourcePin {
        family: EmulatorFamily::AzaharLibretro,
        fork: "azahar",
        repository: "https://github.com/azahar-emu/azahar.git",
        reference: "master",
        revision: "9c38437daad90a2f05f55a047d04d4073a476456",
        systems: &["3ds"],
    },
    SourcePin {
        family: EmulatorFamily::EdenFamily,
        fork: "eden",
        repository: "https://git.eden-emu.dev/eden-emu/eden.git",
        reference: "master",
        revision: "5df599128d6828fa0e42968909da848c255d22b1",
        systems: &["switch"],
    },
    SourcePin {
        family: EmulatorFamily::EdenFamily,
        fork: "eden-nx2",
        repository: "https://git.eden-emu.dev/Takoroka/eden-nx2.git",
        reference: "eden-nx2",
        revision: "50fa86bbbc403ad565eb44fcc281f16f77c69e15",
        systems: &["switch", "switch2"],
    },
    SourcePin {
        family: EmulatorFamily::EdenFamily,
        fork: "eglantine",
        repository: "https://github.com/Djihads80/Eglantine.git",
        reference: "nx2",
        revision: "c54bc2289bfffda7fa3cc4c3a8cf522d84a10fd4",
        systems: &["switch", "switch2"],
    },
];

pub fn maintained_source(fork: &str) -> Option<&'static SourcePin> {
    MAINTAINED_SOURCES.iter().find(|pin| pin.fork == fork)
}

fn hex_digest(value: &str, lengths: &[usize]) -> bool {
    lengths.contains(&value.len()) && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn unique(values: &[String]) -> bool {
    let mut seen = std::collections::BTreeSet::new();
    values.iter().all(|value| seen.insert(value))
}

fn token(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.'))
}

impl BuildProfile {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema != BUILD_PROFILE_SCHEMA || self.bridge_api != BRIDGE_API_VERSION {
            return Err("unsupported emulator build schema or bridge API".into());
        }
        if !token(&self.fork)
            || !token(&self.target)
            || self.repository.is_empty()
            || self.repository.len() > 2048
            || self.repository.chars().any(char::is_control)
            || !hex_digest(&self.revision, &[40, 64])
            || !hex_digest(&self.patch_sha256, &[64])
        {
            return Err("emulator build requires explicit valid source/build provenance".into());
        }
        let (systems, renderers): (&[&str], &[&str]) = match self.family {
            EmulatorFamily::AzaharLibretro => (&["3ds"], &["software"]),
            EmulatorFamily::EdenFamily => (&["switch", "switch2"], &["vulkan", "opengl"]),
        };
        if self.systems.is_empty()
            || self.renderers.is_empty()
            || !unique(&self.systems)
            || !unique(&self.renderers)
            || self
                .systems
                .iter()
                .any(|system| !systems.contains(&system.as_str()))
            || self
                .renderers
                .iter()
                .any(|renderer| !renderers.contains(&renderer.as_str()))
            || !unique(&self.cpu_features)
            || self.cpu_features.iter().any(|feature| !token(feature))
        {
            return Err("invalid emulator system, renderer or CPU feature domain".into());
        }
        if let Some(pin) = maintained_source(&self.fork) {
            if self.family != pin.family
                || self.repository != pin.repository
                || self.revision != pin.revision
                || self
                    .systems
                    .iter()
                    .any(|system| !pin.systems.contains(&system.as_str()))
            {
                return Err("maintained fork profile does not match its pinned source".into());
            }
        }
        Ok(())
    }

    pub fn validate_selection(&self, system: &str, renderer: &str) -> Result<(), String> {
        self.validate()?;
        if !self.systems.iter().any(|candidate| candidate == system) {
            return Err("selected system is not supported by this emulator build".into());
        }
        if !self.renderers.iter().any(|candidate| candidate == renderer) {
            return Err("selected renderer is not supported by this emulator build".into());
        }
        Ok(())
    }

    /// Compare a selected sidecar/profile with runtime readback. This never replaces the
    /// launch-bound producer authentication exchange or validates advertised operation semantics.
    pub fn validate_hello(&self, hello: &Value) -> Result<(), String> {
        self.validate()?;
        if hello.get("session_token").is_some() {
            return Err("hello must not disclose producer credentials".into());
        }
        if hello.get("protocol_version").and_then(Value::as_u64) != Some(1)
            || hello.get("adapter").and_then(Value::as_str) != Some(self.family.adapter())
        {
            return Err("emulator hello protocol or family does not match selected build".into());
        }
        let runtime: Self = serde_json::from_value(
            hello
                .get("host_build")
                .cloned()
                .ok_or("hello lacks emulator build profile")?,
        )
        .map_err(|_| "hello has an invalid emulator build profile")?;
        if runtime != *self {
            return Err("emulator live build does not match selected metadata".into());
        }
        self.validate_selection(
            hello
                .get("system")
                .and_then(Value::as_str)
                .ok_or("hello lacks system")?,
            hello
                .get("renderer")
                .and_then(Value::as_str)
                .ok_or("hello lacks renderer")?,
        )
    }
}

#[cfg(test)]
#[path = "emulator_profile_tests.rs"]
mod tests;

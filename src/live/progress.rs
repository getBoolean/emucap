//! Bounded observation of native presents while a guest is already running.
//! This capability does not establish a pause barrier, exact stepping or deterministic execution.
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const METHOD: &str = "wait_for_running_frames";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ProgressCapability {
    pub domain: String,
    pub max_count: u64,
    pub max_timeout_ms: u64,
    pub overshoot: bool,
    pub running_only: bool,
}

impl ProgressCapability {
    pub fn from_hello(value: &Value) -> Result<Self, String> {
        let capability: Self = serde_json::from_value(value.clone()).map_err(|e| e.to_string())?;
        if !matches!(
            capability.domain.as_str(),
            "native_guest_present" | "libretro_present"
        ) || capability.max_count == 0
            || capability.max_count > super::temporal::MAX_SYNC_ADVANCE_COUNT
            || capability.max_timeout_ms == 0
            || capability.max_timeout_ms > super::temporal::MAX_SYNC_OPERATION_MS
            || !capability.overshoot
            || !capability.running_only
        {
            return Err("invalid observed-progress capability".into());
        }
        Ok(capability)
    }

    pub fn validate_request(&self, count: u64, timeout_ms: u64) -> Result<(), String> {
        if count == 0
            || count > self.max_count
            || timeout_ms == 0
            || timeout_ms > self.max_timeout_ms
        {
            return Err("progress request exceeds advertised count or timeout bounds".into());
        }
        Ok(())
    }

    /// Validate a terminal without equating native progress with host polls or exact stepping.
    pub fn validate_terminal(&self, value: &Value, requested: u64) -> Result<(), String> {
        let number = |key| {
            value
                .get(key)
                .and_then(Value::as_u64)
                .ok_or_else(|| format!("progress terminal lacks {key}"))
        };
        let start = number("start")?;
        let end = number("end")?;
        let observed = end
            .checked_sub(start)
            .ok_or("native progress counter went backwards")?;
        let status = value.get("status").and_then(Value::as_str);
        let state = value.get("state").and_then(Value::as_str);
        if value.get("domain").and_then(Value::as_str) != Some(self.domain.as_str())
            || number("requested")? != requested
            || number("observed")? != observed
            || number("overshoot")? != observed.saturating_sub(requested)
            || !matches!(status, Some("completed" | "timed_out" | "interrupted"))
            || !matches!(state, Some("running" | "frozen"))
            || (status == Some("completed") && (observed < requested || state != Some("running")))
        {
            return Err("invalid observed-progress terminal".into());
        }
        Ok(())
    }
}

#[cfg(test)]
#[path = "progress_tests.rs"]
mod tests;

use super::*;
use crate::live::link::FeatureCapabilities;
use serde_json::json;

fn capability() -> serde_json::Value {
    json!({"domain":"native_guest_present","max_count":5000,"max_timeout_ms":250000,
        "overshoot":true,"running_only":true})
}

#[test]
fn observed_progress_requires_its_typed_capability_pair() {
    let methods = vec![METHOD.into()];
    let hello = json!({"progress_capability":capability()});
    let parsed = FeatureCapabilities::from_hello(&hello, &methods, &[]).unwrap();
    assert_eq!(parsed.progress.unwrap().domain, "native_guest_present");
    assert!(FeatureCapabilities::from_hello(&hello, &[], &[]).is_err());
    assert!(FeatureCapabilities::from_hello(&json!({}), &methods, &[]).is_err());
}

#[test]
fn host_calls_and_exactness_cannot_masquerade_as_observed_presents() {
    for (key, value) in [
        ("domain", json!("retro_run_calls")),
        ("domain", json!("instructions")),
        ("max_count", json!(5001)),
        ("max_count", json!(0)),
        ("max_timeout_ms", json!(250001)),
        ("max_timeout_ms", json!(0)),
        ("overshoot", json!(false)),
        ("running_only", json!(false)),
    ] {
        let mut invalid = capability();
        invalid[key] = value;
        assert!(
            ProgressCapability::from_hello(&invalid).is_err(),
            "{invalid}"
        );
    }
    let mut invalid = capability();
    invalid["exact"] = json!(true);
    assert!(ProgressCapability::from_hello(&invalid).is_err());
}

#[test]
fn request_and_terminal_validation_preserve_observed_delta_and_state() {
    let cap = ProgressCapability::from_hello(&capability()).unwrap();
    assert!(cap.validate_request(10, 1000).is_ok());
    assert!(cap.validate_request(0, 1000).is_err());
    assert!(cap.validate_request(1, 250001).is_err());
    let terminal = json!({"status":"completed","domain":"native_guest_present",
        "requested":10,"start":50,"end":62,"observed":12,"overshoot":2,"state":"running"});
    assert!(cap.validate_terminal(&terminal, 10).is_ok());
    let mut invalid = terminal.clone();
    invalid["observed"] = json!(10);
    assert!(cap.validate_terminal(&invalid, 10).is_err());
    invalid = terminal.clone();
    invalid["state"] = json!("frozen");
    assert!(cap.validate_terminal(&invalid, 10).is_err());
    invalid = terminal;
    invalid["end"] = json!(49);
    assert!(cap.validate_terminal(&invalid, 10).is_err());
}

#[test]
fn wait_cancellation_does_not_require_or_enable_exact_steps() {
    let methods = vec![METHOD.into(), "cancel_operation".into()];
    let hello = json!({"progress_capability":capability(),
        "temporal_cancellation_capability":{"methods":[METHOD],"control_service_ms":25,"stop_host_ms":500}});
    let parsed = FeatureCapabilities::from_hello(&hello, &methods, &[]).unwrap();
    assert!(parsed.temporal_cancellation.is_some());
    assert!(!methods.iter().any(|method| method == "step"));
}

use super::*;
use crate::live::link::{Capabilities, ProgressCallControl, ProgressObserver, RequestCancellation};
use crate::live::progress::ProgressCapability;
use crate::live::temporal::CancellationCapability;

struct WaitLink {
    capabilities: Capabilities,
    calls: Vec<String>,
    state: &'static str,
    terminal: Value,
    cancellation_seen: bool,
}

impl WaitLink {
    fn new() -> Self {
        let mut capabilities = Capabilities::empty();
        capabilities.identity.launch_id = Some("launch-wait".into());
        capabilities.features.progress = Some(ProgressCapability {
            domain: "native_render_present".into(),
            max_count: 50,
            max_timeout_ms: 1000,
            overshoot: true,
            running_only: true,
        });
        capabilities.features.temporal_cancellation = Some(CancellationCapability {
            methods: vec!["wait_for_running_frames".into()],
            control_service_ms: 25,
            stop_host_ms: 500,
        });
        Self {
            capabilities,
            calls: vec![],
            state: "running",
            cancellation_seen: false,
            terminal: json!({"status":"completed","domain":"native_render_present",
                "requested":10,"start":40,"end":52,"observed":12,"overshoot":2,"state":"running"}),
        }
    }
}

impl EmulatorLink for WaitLink {
    fn capabilities(&self) -> &Capabilities {
        &self.capabilities
    }
    fn attachment_id(&self) -> Option<&str> {
        Some("attachment-wait")
    }
    fn call(&mut self, method: &str, _: Value) -> Result<Value, LinkError> {
        self.calls.push(method.into());
        assert_eq!(
            method, "status",
            "waiting must not pause, resume or inject input"
        );
        Ok(json!({"state":self.state}))
    }
    fn call_with_progress(
        &mut self,
        method: &str,
        params: Value,
        _: &mut ProgressObserver<'_>,
        control: &ProgressCallControl,
    ) -> Result<Value, LinkError> {
        self.calls.push(method.into());
        assert_eq!(method, "wait_for_running_frames");
        assert_eq!(params["frames"], 10);
        assert_eq!(params["timeout_ms"], 1000);
        assert_eq!(params["_control"]["runtime"], "launch-wait");
        assert_eq!(params["_control"]["owner_id"], "attachment-wait");
        assert_eq!(control.abort.as_ref().unwrap().params, params["_control"]);
        assert_eq!(control.temporal_stop_ms, Some(500));
        self.cancellation_seen = control.cancellation.is_cancelled();
        Ok(self.terminal.clone())
    }
}

#[test]
fn running_wait_reports_native_overshoot_without_execution_mutation() {
    let mut link = WaitLink::new();
    let ToolOutput::Json(result) = wait_for_running_frames(
        &mut link,
        10,
        1000,
        RequestCancellation::default(),
        "attachment-wait",
    )
    .unwrap() else {
        panic!()
    };
    assert_eq!(result["observed"], 12);
    assert_eq!(result["overshoot"], 2);
    assert_eq!(link.calls, ["status", "wait_for_running_frames"]);
}

#[test]
fn running_wait_rejects_bounds_paused_state_and_pre_cancel_before_wait() {
    let mut link = WaitLink::new();
    assert!(wait_for_running_frames(
        &mut link,
        51,
        1000,
        RequestCancellation::default(),
        "attachment-wait"
    )
    .is_err());
    assert!(link.calls.is_empty());
    link.state = "frozen";
    assert!(wait_for_running_frames(
        &mut link,
        10,
        1000,
        RequestCancellation::default(),
        "attachment-wait"
    )
    .is_err());
    assert_eq!(link.calls, ["status"]);
    let cancellation = RequestCancellation::default();
    cancellation.cancel();
    assert!(matches!(
        wait_for_running_frames(&mut link, 10, 1000, cancellation, "attachment-wait"),
        Err(LinkError::Cancelled)
    ));
    assert_eq!(link.calls, ["status"]);
}

#[test]
fn running_wait_does_not_accept_a_fabricated_completed_counter() {
    let mut link = WaitLink::new();
    link.terminal["observed"] = json!(10);
    assert!(matches!(
        wait_for_running_frames(
            &mut link,
            10,
            1000,
            RequestCancellation::default(),
            "attachment-wait"
        ),
        Err(LinkError::Protocol(_))
    ));
}

/// Publish the hello-validated static batch/pacing domains and verify the dynamic pacing policy.
/// An invalid live policy is withheld rather than presented as the current setting.
pub(super) fn enrich_feature_capabilities(
    value: &mut serde_json::Value,
    features: &emucap::live::link::FeatureCapabilities,
) {
    let Some(object) = value.as_object_mut() else {
        return;
    };
    object.remove("memory_batch_capability");
    object.remove("execution_speed_capability");
    object.remove("progress_capability");
    object.remove("touch_capability");
    object.remove("temporal_cancellation_capability");
    if let Some(touch) = &features.touch {
        object.insert("touch_capability".into(), serde_json::json!(touch));
        if let Some(methods) = object
            .get_mut("methods")
            .and_then(serde_json::Value::as_array_mut)
        {
            methods.retain(|method| method != "pulse_touch_while_running");
        }
    }
    if let Some(cancel) = &features.temporal_cancellation {
        object.insert(
            "temporal_cancellation_capability".into(),
            serde_json::json!(cancel),
        );
    }
    let progress_ready = features
        .temporal_cancellation
        .as_ref()
        .is_some_and(|cancel| {
            cancel
                .methods
                .iter()
                .any(|method| method == emucap::live::progress::METHOD)
        });
    if let Some(progress) = features.progress.as_ref().filter(|_| progress_ready) {
        object.insert("progress_capability".into(), serde_json::json!(progress));
        if let Some(methods) = object
            .get_mut("methods")
            .and_then(serde_json::Value::as_array_mut)
        {
            if !methods
                .iter()
                .any(|method| method == emucap::live::progress::METHOD)
            {
                methods.push(serde_json::json!(emucap::live::progress::METHOD));
            }
        }
    } else if let Some(methods) = object
        .get_mut("methods")
        .and_then(serde_json::Value::as_array_mut)
    {
        methods.retain(|method| method != emucap::live::progress::METHOD);
    }
    if let Some(batch) = &features.memory_batch {
        object.insert("memory_batch_capability".into(), serde_json::json!(batch));
    }
    let Some(speed) = &features.execution_speed else {
        object.remove("execution_speed");
        return;
    };
    object.insert(
        "execution_speed_capability".into(),
        serde_json::json!(speed),
    );
    if let Some(policy) = object.get("execution_speed") {
        if let Err(error) = speed.verify_policy(policy) {
            object.remove("execution_speed");
            object.insert("execution_speed_error".into(), serde_json::json!(error));
        }
    }
}

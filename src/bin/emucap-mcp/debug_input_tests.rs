use super::*;
use std::collections::BTreeMap;

#[test]
fn advertised_touch_geometry_validates_before_dispatch() {
    let status = serde_json::json!({"touch_capability":{"ports":[0],"width":320,
        "height":240,"coordinate_space":"touchscreen","contacts":1}});
    assert!(validate_touch(&status, 0, Some(319), Some(239), None, false).is_ok());
    for (port, x, y, frames) in [
        (1, 319, 239, None),
        (0, 320, 239, None),
        (0, 319, 240, None),
        (0, 0, 0, Some(1)),
    ] {
        assert!(validate_touch(&status, port, Some(x), Some(y), frames, false).is_err());
    }
    assert!(validate_touch(&status, 0, None, None, None, true).is_ok());
    assert!(validate_touch(&serde_json::json!({}), 0, Some(256), Some(0), None, false).is_err());
}

#[test]
fn debug_describe_projects_touch_and_native_progress_capabilities() {
    let status = serde_json::json!({"contracts":{"state":"validated"},
        "methods":["hold_touch","release_touch","wait_for_running_frames"],
        "touch_capability":{"ports":[0],"width":1280,"height":720,"coordinate_space":"touchscreen","contacts":1},
        "progress_capability":{"domain":"native_render_present","max_count":50,"max_timeout_ms":1000,"overshoot":true,"running_only":true}});
    let result = crate::debug_surface::describe(&status);
    assert_eq!(result["touch_capability"], status["touch_capability"]);
    assert_eq!(result["progress_capability"], status["progress_capability"]);
    assert!(
        result["operations"]["wait_for_running_frames"]["arguments_schema"]["properties"]["frames"]
            .is_object()
    );
    assert!(result["operations"]["pulse_touch_while_running"].is_null());
}

fn xbox_axis_status() -> Value {
    serde_json::json!({
        "contracts": {"state":"validated"},
        "capability_revision":"revision-xbox",
        "methods":["set_input"],
        "input_buttons":{"buttons":["a"]},
        "input_axes": {
            "ports":[{
                "port":0,
                "axes":{
                    "left_x":{"minimum":-32768, "neutral":0, "maximum":32767},
                    "right_trigger":{"minimum":0, "neutral":0, "maximum":32767}
                }
            }]
        }
    })
}

#[test]
fn describe_projects_live_axis_capability_next_to_the_set_input_schema() {
    let status = xbox_axis_status();
    let description = crate::debug_surface::describe(&status);
    assert_eq!(description["input_axes"], status["input_axes"]);
    assert!(description["operations"]["set_input"]["arguments_schema"]
        .to_string()
        .contains("axes"));
}

#[test]
fn axis_validation_accepts_only_the_advertised_port_names_and_ranges() {
    let status = xbox_axis_status();
    assert!(validate_controller_axes(
        &status,
        0,
        &BTreeMap::from([("left_x".into(), -32768), ("right_trigger".into(), 32767)])
    )
    .is_ok());

    for (port, axes) in [
        (1, BTreeMap::from([("left_x".into(), 0)])),
        (0, BTreeMap::from([("left_x".into(), 32768)])),
        (0, BTreeMap::from([("throttle".into(), 1)])),
    ] {
        assert!(validate_controller_axes(&status, port, &axes).is_err());
    }
    assert!(validate_controller_axes(&Value::Null, 0, &BTreeMap::new()).is_ok());
}

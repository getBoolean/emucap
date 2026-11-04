use super::*;
use std::process::Command;

fn python() -> Option<PathBuf> {
    if let Some(value) = std::env::var_os("EMUCAP_TEST_PYTHON") {
        return Some(value.into());
    }
    #[cfg(windows)]
    let result = Command::new("py")
        .args(["-3.12", "-c", "import sys; print(sys.executable)"])
        .output();
    #[cfg(not(windows))]
    let result = Command::new("python3")
        .args(["-c", "import sys; print(sys.executable)"])
        .output();
    result
        .ok()
        .filter(|output| output.status.success())
        .map(|output| PathBuf::from(String::from_utf8_lossy(&output.stdout).trim()))
}

fn scripted_worker(script: &str) -> (tempfile::TempDir, WorkerProcess) {
    let root = tempfile::tempdir().unwrap();
    let path = root.path().join("worker.py");
    std::fs::write(&path, script).unwrap();
    let mut command = Command::new(python().expect("Python is required for Azahar host tests"));
    command.arg("-I").arg("-u").arg(path);
    let worker = WorkerProcess::spawn(command).unwrap();
    (root, worker)
}

#[test]
fn private_worker_reply_is_bounded_and_identity_checked() {
    let (_root, mut worker) = scripted_worker(
        "import sys,json\nfor line in sys.stdin:\n r=json.loads(line); print(json.dumps({'id':r['id'],'ok':True,'result':{'alive':True}}),flush=True)\n",
    );
    let reply = worker
        .exchange(
            &Request::new(3, "status", json!({})),
            Duration::from_secs(5),
            &RequestCancellation::default(),
        )
        .unwrap();
    assert_eq!(reply.result.unwrap()["alive"], true);
    let identity = worker.identity.clone();
    worker.terminate().unwrap();
    assert_eq!(
        crate::live::runtime::process_state(&identity),
        crate::live::runtime::ProcessState::Exited
    );
}

#[test]
fn mismatched_reply_retires_child_instead_of_reusing_channel() {
    let (_root, mut worker) = scripted_worker(
        "import sys,json\nfor line in sys.stdin:\n print(json.dumps({'id':999,'ok':True,'result':{}}),flush=True)\n",
    );
    assert!(worker
        .exchange(
            &Request::new(3, "status", json!({})),
            Duration::from_secs(5),
            &RequestCancellation::default(),
        )
        .is_err());
    assert!(worker.retired);
    assert!(worker.child.try_wait().unwrap().is_some());
}

#[test]
fn hung_worker_deadline_and_cancellation_verify_exit() {
    for cancelled in [false, true] {
        let (_root, mut worker) = scripted_worker("import time\nwhile True: time.sleep(1)\n");
        let cancellation = RequestCancellation::default();
        if cancelled {
            cancellation.cancel();
        }
        let started = Instant::now();
        let error = worker
            .exchange(
                &Request::new(1, "run_frames", json!({"count": 1})),
                Duration::from_millis(150),
                &cancellation,
            )
            .unwrap_err();
        assert!(matches!(
            error.kind(),
            io::ErrorKind::TimedOut | io::ErrorKind::Interrupted
        ));
        assert!(started.elapsed() < Duration::from_secs(6));
        assert!(worker.child.try_wait().unwrap().is_some());
    }
}

#[test]
fn oversized_or_malformed_worker_output_retires_child() {
    for script in [
        "import sys\nsys.stdin.readline(); print('x'*(8*1024*1024+1),flush=True)\n",
        "import sys\nsys.stdin.readline(); print('not-json',flush=True)\n",
    ] {
        let (_root, mut worker) = scripted_worker(script);
        assert!(worker
            .exchange(
                &Request::new(1, "hello", json!({})),
                Duration::from_secs(5),
                &RequestCancellation::default(),
            )
            .is_err());
        assert!(worker.child.try_wait().unwrap().is_some());
    }
}

#[test]
fn active_native_cancellation_retires_before_the_request_deadline() {
    let (_root, mut worker) = scripted_worker("import time\nwhile True: time.sleep(1)\n");
    let identity = worker.identity.clone();
    let cancellation = RequestCancellation::default();
    let trigger = cancellation.clone();
    let cancel_thread = std::thread::spawn(move || {
        std::thread::sleep(Duration::from_millis(50));
        trigger.cancel();
    });
    let started = Instant::now();
    let error = worker
        .exchange(
            &Request::new(1, "status", json!({})),
            Duration::from_secs(5),
            &cancellation,
        )
        .unwrap_err();
    cancel_thread.join().unwrap();
    assert_eq!(error.kind(), io::ErrorKind::Interrupted);
    assert!(started.elapsed() < Duration::from_secs(3));
    assert!(worker.retired);
    assert_eq!(
        crate::live::runtime::process_state(&identity),
        crate::live::runtime::ProcessState::Exited
    );
}

fn host_fixture() -> (tempfile::TempDir, AzaharHost) {
    let root = tempfile::tempdir().unwrap();
    let script = root.path().join("worker.py");
    std::fs::write(&script, r#"import json,sys,pathlib
profile=json.load(open(sys.argv[sys.argv.index('--profile')+1]))
effective=pathlib.Path(sys.argv[sys.argv.index('--directory')+1])/'Azahar'
effective.mkdir(parents=True,exist_ok=True)
presents=0
for line in sys.stdin:
    request=json.loads(line)
    method=request['method']
    if method=='hello':
        result={'protocol_version':1,'adapter':'azahar-libretro','system':'3ds','renderer':'software','geometry':[400,480],
                'host_build':profile,'effective_core_user_root':str(effective.resolve())}
    elif method=='screenshot':
        result={'width':1,'height':1,'png_base64':'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='}
    else:
        presents+=1
        result={'host_run_calls':0,'software_presentations':presents,'state':'running','paused':False}
    print(json.dumps({'id':request['id'],'ok':True,'result':result}),flush=True)
"#).unwrap();
    let profile = root.path().join("profile.json");
    std::fs::write(
        &profile,
        serde_json::to_vec(&json!({
            "schema":"emucap-emulator-build/v1","family":"azahar-libretro","fork":"azahar",
            "repository":"https://github.com/azahar-emu/azahar.git",
            "revision":"9c38437daad90a2f05f55a047d04d4073a476456",
            "patch_sha256":"0".repeat(64),"bridge_api":1,"systems":["3ds"],"renderers":["software"],
            "cpu_features":[],"target":"test-host"
        }))
        .unwrap(),
    )
    .unwrap();
    let content = root.path().join("fixture.3dsx");
    std::fs::write(&content, b"lawful host contract fixture").unwrap();
    let receipt = root.path().join("receipt.json");
    let python = python().expect("Python is required for Azahar host tests");
    let host = AzaharHost::prepare(&HostConfig {
        python: &python,
        worker: &script,
        core: &root.path().join("fake-core"),
        content: &content,
        directory: &root.path().join("data"),
        profile: &profile,
        launch_id: "launch-01arz3ndektsv4rrffq69g5fav",
        receipt: &receipt,
    })
    .unwrap();
    let recorded: StartupReceipt =
        serde_json::from_slice(&std::fs::read(receipt).unwrap()).unwrap();
    assert_eq!(recorded.worker, host.worker.identity);
    assert_eq!(recorded.host.pid, std::process::id());
    (root, host)
}

#[test]
fn owned_host_authenticates_and_reaches_existing_screenshot_tool() {
    use crate::live::link::EmulatorLink;
    use crate::live::producer_auth::{derive_front_key, Boundary};
    use crate::live::reconnect::{
        cancellation::TemporalAdmission, owned::serve_reconnecting_owned,
    };
    use std::sync::atomic::{AtomicBool, Ordering};

    let _lock = crate::test_env::lock_env();
    let _environment = crate::test_env::EnvGuard::new(&[
        "EMUCAP_EMU_HOME",
        "EMUCAP_SESSION_TOKEN",
        "EMUCAP_LAUNCH_ID",
    ]);
    let (root, host) = host_fixture();
    std::env::set_var("EMUCAP_EMU_HOME", root.path().join("managed"));
    let mut link = crate::live::tcp::bind("127.0.0.1:0", Duration::from_secs(5)).unwrap();
    let port = link.local_addr().port();
    let launch_id = "launch-01arz3ndektsv4rrffq69g5fav";
    let credential = derive_front_key(
        link.session_token().unwrap(),
        Boundary::Direct,
        port,
        launch_id,
    )
    .unwrap();
    std::env::set_var("EMUCAP_SESSION_TOKEN", credential);
    std::env::set_var("EMUCAP_LAUNCH_ID", launch_id);
    let finished = Arc::new(AtomicBool::new(false));
    let completed = Arc::clone(&finished);
    let mut native_probe = host.terminal_probe();
    let server = std::thread::spawn(move || {
        serve_reconnecting_owned(
            port,
            "azahar-test",
            host,
            move || {
                if completed.load(Ordering::Acquire) {
                    Some("test completed".into())
                } else {
                    native_probe()
                }
            },
            TemporalAdmission {
                runtime: launch_id.into(),
                methods: vec!["wait_for_running_frames".into()],
            },
        )
    });
    let status = link.call("status", json!({})).unwrap();
    assert_eq!(status["system"], "3ds");
    assert_eq!(status["host_build"]["family"], "azahar-libretro");
    assert!(link
        .capabilities()
        .methods
        .iter()
        .all(|method| method != "step"));
    assert!(link.capabilities().identity.session_token.is_none());
    assert!(matches!(
        crate::live::tools::screenshot(&mut link, None).unwrap(),
        crate::live::tools::ToolOutput::Image { .. }
    ));
    assert!(!link
        .call("step", json!({"frames":1}))
        .unwrap_err()
        .to_string()
        .is_empty());
    finished.store(true, Ordering::Release);
    drop(link);
    server.join().unwrap().unwrap();
}

#[test]
fn running_wait_counts_presentations_and_leaves_worker_alive_on_interrupt_or_timeout() {
    let (_root, mut host) = host_fixture();
    let cap =
        crate::live::progress::ProgressCapability::from_hello(&host.hello()["progress_capability"])
            .unwrap();
    for (frames, timeout, cancelled, terminal) in [
        (3, 1000, false, "completed"),
        (5000, 1, false, "timed_out"),
        (5000, 1000, true, "interrupted"),
    ] {
        let cancellation = RequestCancellation::default();
        if cancelled {
            cancellation.cancel();
        }
        let response = host
            .response(
                Request::new(
                    77,
                    "wait_for_running_frames",
                    json!({"frames":frames,"timeout_ms":timeout}),
                ),
                &cancellation,
            )
            .unwrap();
        let value = response.result.unwrap();
        assert_eq!(value["status"], terminal);
        cap.validate_terminal(&value, frames).unwrap();
        assert!(!host.worker.retired);
        assert!(host.worker.child.try_wait().unwrap().is_none());
    }
    let rejected = host
        .response(
            Request::new(
                78,
                "wait_for_running_frames",
                json!({"frames":0,"timeout_ms":5}),
            ),
            &RequestCancellation::default(),
        )
        .unwrap();
    assert!(!rejected.ok);
    assert!(!host.worker.retired);
}

#[test]
fn stalled_native_owner_retires_instead_of_reporting_a_normal_wait_timeout() {
    let (_root, mut host) = host_fixture();
    let (_script, hung) =
        scripted_worker("import sys,time\nsys.stdin.readline()\ntime.sleep(60)\n");
    host.worker = hung;
    let before = Instant::now();
    assert!(host
        .response(
            Request::new(
                2,
                "wait_for_running_frames",
                json!({"frames":1,"timeout_ms":1})
            ),
            &RequestCancellation::default()
        )
        .is_err());
    assert!(host.worker.retired);
    assert!(host.worker.child.try_wait().unwrap().is_some());
    assert!(before.elapsed() < Duration::from_secs(6));
}

#[cfg(any(windows, target_os = "linux"))]
#[test]
fn supervisor_fixture_child() {
    let Some(receipt) = std::env::var_os("EMUCAP_TEST_SUPERVISOR_RECEIPT") else {
        return;
    };
    let mut command = Command::new(python().expect("test Python"));
    command.args(["-I", "-u", "-c", "import time; time.sleep(60)"]);
    let worker = WorkerProcess::spawn(command).unwrap();
    std::fs::write(receipt, serde_json::to_vec(&worker.identity).unwrap()).unwrap();
    std::thread::sleep(Duration::from_secs(60));
    drop(worker);
}

#[cfg(any(windows, target_os = "linux"))]
#[test]
fn killing_supervisor_also_terminates_its_worker() {
    let root = tempfile::tempdir().unwrap();
    let receipt = root.path().join("worker.json");
    let mut supervisor = Command::new(std::env::current_exe().unwrap())
        .args([
            "--exact",
            "azahar_host::tests::supervisor_fixture_child",
            "--nocapture",
        ])
        .env("EMUCAP_TEST_SUPERVISOR_RECEIPT", &receipt)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::inherit())
        .spawn()
        .unwrap();
    let deadline = Instant::now() + Duration::from_secs(10);
    while !receipt.exists() {
        assert!(
            Instant::now() < deadline,
            "supervisor did not publish worker identity"
        );
        assert!(
            supervisor.try_wait().unwrap().is_none(),
            "supervisor exited before receipt"
        );
        std::thread::sleep(POLL);
    }
    let worker: ProcessIdentity = serde_json::from_slice(&std::fs::read(receipt).unwrap()).unwrap();
    supervisor.kill().unwrap();
    supervisor.wait().unwrap();
    let deadline = Instant::now() + Duration::from_secs(5);
    while crate::live::runtime::process_state(&worker) != crate::live::runtime::ProcessState::Exited
    {
        assert!(Instant::now() < deadline, "worker outlived supervisor");
        std::thread::sleep(POLL);
    }
}

//! Supervised libretro worker. Core crashes/hangs retire one owned process generation.
use std::io::{self, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex};
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::emulator_profile::{BuildProfile, EmulatorFamily};
use crate::live::control_session::{Attachment, EventKind, SessionEvent};
use crate::live::link::RequestCancellation;
use crate::live::protocol::{read_ndjson_frame, ProtocolError, Request, Response};
use crate::live::reconnect::owned::OwnedHandler;
use crate::live::reconnect::{BridgeDirective, BridgeReply};
use crate::live::runtime::{capture_process, ProcessIdentity};

const WORKER_REQUEST_BYTES: usize = 64 * 1024;
const NATIVE_TIMEOUT: Duration = Duration::from_secs(30);
const CLEANUP_TIMEOUT: Duration = Duration::from_secs(5);
const POLL: Duration = Duration::from_millis(20);

struct WorkerProcess {
    child: Child,
    identity: ProcessIdentity,
    requests: Option<mpsc::SyncSender<Vec<u8>>>,
    replies: mpsc::Receiver<io::Result<Response>>,
    terminal: Arc<Mutex<Option<String>>>,
    retired: bool,
    #[cfg(windows)]
    _job: WorkerJob,
}

#[cfg(windows)]
struct WorkerJob(isize);

#[cfg(windows)]
impl WorkerJob {
    fn attach(child: &Child) -> io::Result<Self> {
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::Foundation::CloseHandle;
        use windows_sys::Win32::System::JobObjects::*;
        let handle = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
        if handle.is_null() {
            return Err(io::Error::last_os_error());
        }
        let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let result = unsafe {
            SetInformationJobObject(
                handle,
                JobObjectExtendedLimitInformation,
                &limits as *const _ as *const _,
                std::mem::size_of_val(&limits) as u32,
            )
        };
        let attached = result != 0
            && unsafe { AssignProcessToJobObject(handle, child.as_raw_handle() as _) } != 0;
        if !attached {
            let error = io::Error::last_os_error();
            unsafe {
                CloseHandle(handle);
            }
            return Err(error);
        }
        Ok(Self(handle as isize))
    }
}

#[cfg(windows)]
impl Drop for WorkerJob {
    fn drop(&mut self) {
        unsafe {
            windows_sys::Win32::Foundation::CloseHandle(self.0 as _);
        }
    }
}

fn invalid(message: impl ToString) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message.to_string())
}

fn terminal(terminal: &Mutex<Option<String>>, message: impl ToString) {
    let mut reason = terminal.lock().unwrap_or_else(|error| error.into_inner());
    if reason.is_none() {
        *reason = Some(message.to_string());
    }
}

impl WorkerProcess {
    fn spawn(mut command: Command) -> io::Result<Self> {
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());
        command
            .env_remove("EMUCAP_SESSION_TOKEN")
            .env_remove("EMUCAP_NATIVE_DEBUG_TOKEN");
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            use windows_sys::Win32::System::Threading::CREATE_NO_WINDOW;
            command.creation_flags(CREATE_NO_WINDOW);
        }
        #[cfg(target_os = "linux")]
        {
            use std::os::unix::process::CommandExt;
            let parent = std::process::id();
            unsafe {
                command.pre_exec(move || {
                    if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) != 0 {
                        return Err(io::Error::last_os_error());
                    }
                    if libc::getppid() as u32 != parent {
                        libc::_exit(98);
                    }
                    Ok(())
                });
            }
        }
        let mut child = command.spawn()?;
        #[cfg(windows)]
        let job = match WorkerJob::attach(&child) {
            Ok(job) => job,
            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(error);
            }
        };
        let identity = capture_process(child.id());
        if identity.start_identity.is_none() {
            let _ = child.kill();
            let _ = child.wait();
            return Err(invalid("worker process start identity is unavailable"));
        }
        let mut writer = child.stdin.take().expect("piped child stdin");
        let stdout = child.stdout.take().expect("piped child stdout");
        let (request_tx, request_rx) = mpsc::sync_channel::<Vec<u8>>(1);
        let (reply_tx, reply_rx) = mpsc::sync_channel(1);
        let write_errors = reply_tx.clone();
        let state = Arc::new(Mutex::new(None));
        let read_terminal = Arc::clone(&state);
        std::thread::spawn(move || {
            while let Ok(request) = request_rx.recv() {
                if let Err(error) = writer.write_all(&request).and_then(|_| writer.flush()) {
                    let _ = write_errors.try_send(Err(error));
                    return;
                }
            }
        });
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            let mut pending = Vec::new();
            loop {
                let response = match read_ndjson_frame(&mut reader, &mut pending) {
                    Ok(Some(line)) => serde_json::from_str(&line).map_err(invalid),
                    Ok(None) => Err(io::Error::new(
                        io::ErrorKind::UnexpectedEof,
                        "libretro worker exited",
                    )),
                    Err(error) => Err(error),
                };
                let failed = response.is_err();
                if failed {
                    terminal(
                        &read_terminal,
                        "libretro worker output ended or became invalid",
                    );
                }
                if reply_tx.send(response).is_err() || failed {
                    return;
                }
            }
        });
        Ok(Self {
            child,
            identity,
            requests: Some(request_tx),
            replies: reply_rx,
            terminal: state,
            retired: false,
            #[cfg(windows)]
            _job: job,
        })
    }

    fn terminate(&mut self) -> io::Result<()> {
        self.retired = true;
        self.requests.take();
        if self.child.try_wait()?.is_some() {
            return Ok(());
        }
        if let Err(error) = self.child.kill() {
            if self.child.try_wait()?.is_none() {
                return Err(error);
            }
        }
        let deadline = Instant::now() + CLEANUP_TIMEOUT;
        loop {
            if self.child.try_wait()?.is_some() {
                return Ok(());
            }
            if Instant::now() >= deadline {
                return Err(io::Error::new(
                    io::ErrorKind::TimedOut,
                    "worker termination was not verified",
                ));
            }
            std::thread::sleep(POLL);
        }
    }

    fn retire_error(&mut self, error: io::Error) -> io::Error {
        terminal(&self.terminal, &error);
        match self.terminate() {
            Ok(()) => error,
            Err(cleanup) => io::Error::other(format!("{error}; cleanup failed: {cleanup}")),
        }
    }

    fn exchange(
        &mut self,
        request: &Request,
        budget: Duration,
        cancel: &RequestCancellation,
    ) -> io::Result<Response> {
        if self.retired {
            return Err(io::Error::new(
                io::ErrorKind::BrokenPipe,
                "worker generation is retired",
            ));
        }
        if cancel.is_cancelled() {
            return Err(self.retire_error(io::Error::new(
                io::ErrorKind::Interrupted,
                "native request cancelled before submission; worker terminated",
            )));
        }
        let mut bytes = serde_json::to_vec(request).map_err(invalid)?;
        if bytes.len() >= WORKER_REQUEST_BYTES {
            return Err(invalid("private worker request exceeds byte bound"));
        }
        bytes.push(b'\n');
        self.requests
            .as_ref()
            .ok_or_else(|| invalid("worker channel closed"))?
            .try_send(bytes)
            .map_err(|error| invalid(format!("worker request channel: {error}")))?;
        let deadline = Instant::now() + budget.min(NATIVE_TIMEOUT);
        loop {
            if cancel.is_cancelled() {
                return Err(self.retire_error(io::Error::new(
                    io::ErrorKind::Interrupted,
                    "native request cancelled; worker terminated",
                )));
            }
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                return Err(self.retire_error(io::Error::new(
                    io::ErrorKind::TimedOut,
                    "native request deadline; worker terminated",
                )));
            }
            match self.replies.recv_timeout(remaining.min(POLL)) {
                Ok(Ok(response)) if response.id == request.id => {
                    if response.ok != response.result.is_some()
                        || response.ok == response.error.is_some()
                    {
                        return Err(
                            self.retire_error(invalid("malformed worker response envelope"))
                        );
                    }
                    return Ok(response);
                }
                Ok(Ok(_)) => {
                    return Err(self.retire_error(invalid("worker response identity mismatch")))
                }
                Ok(Err(error)) => return Err(self.retire_error(error)),
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    return Err(self.retire_error(invalid("worker reply channel closed")));
                }
                Err(mpsc::RecvTimeoutError::Timeout) => {
                    if self.child.try_wait()?.is_some() {
                        return Err(
                            self.retire_error(invalid("worker exited before request completed"))
                        );
                    }
                }
            }
        }
    }
}

impl Drop for WorkerProcess {
    fn drop(&mut self) {
        let _ = self.terminate();
    }
}

pub struct HostConfig<'a> {
    pub python: &'a Path,
    pub worker: &'a Path,
    pub core: &'a Path,
    pub content: &'a Path,
    pub directory: &'a Path,
    pub profile: &'a Path,
    pub launch_id: &'a str,
    pub receipt: &'a Path,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StartupReceipt {
    pub schema_version: u32,
    pub launch_id: String,
    pub host: ProcessIdentity,
    pub worker: ProcessIdentity,
}

pub struct AzaharHost {
    worker: WorkerProcess,
    profile: BuildProfile,
    launch_id: String,
    content: PathBuf,
    directory: PathBuf,
    rom_sha1: String,
    worker_hello: Value,
}

impl AzaharHost {
    pub fn prepare(config: &HostConfig<'_>) -> io::Result<Self> {
        if config.launch_id.is_empty() {
            return Err(invalid("Azahar requires a managed launch identity"));
        }
        let mut bytes = Vec::new();
        crate::path_safety::open_regular_file_no_follow(config.profile)?
            .take(128 * 1024 + 1)
            .read_to_end(&mut bytes)?;
        if bytes.len() > 128 * 1024 {
            return Err(invalid("Azahar build profile is oversized"));
        }
        let profile: BuildProfile = serde_json::from_slice(&bytes).map_err(invalid)?;
        profile
            .validate_selection("3ds", "software")
            .map_err(invalid)?;
        if profile.family != EmulatorFamily::AzaharLibretro {
            return Err(invalid("Azahar requires a libretro family build profile"));
        }
        let content = config.content.canonicalize()?;
        std::fs::create_dir_all(config.directory)?;
        let directory = config.directory.canonicalize()?;
        let rom_sha1 = crate::rom::sha1_of_file(&content)?;
        let mut command = Command::new(config.python);
        command
            .args(["-I", "-u"])
            .arg(config.worker)
            .arg("--core")
            .arg(config.core)
            .arg("--rom")
            .arg(&content)
            .arg("--directory")
            .arg(config.directory)
            .arg("--profile")
            .arg(config.profile)
            .arg("--supervisor-pid")
            .arg(std::process::id().to_string());
        if let Some(identity) = capture_process(std::process::id()).start_identity {
            command.arg("--supervisor-start").arg(identity);
        } else {
            return Err(invalid("supervisor process identity is unavailable"));
        }
        let mut worker = WorkerProcess::spawn(command)?;
        write_receipt(config.receipt, config.launch_id, worker.identity.clone())?;
        let response = worker.exchange(
            &Request::new(0, "hello", json!({})),
            NATIVE_TIMEOUT,
            &Default::default(),
        )?;
        if !response.ok {
            return Err(invalid("libretro worker rejected initialization"));
        }
        let worker_hello = response
            .result
            .ok_or_else(|| invalid("worker hello missing result"))?;
        if worker_hello.get("protocol_version").and_then(Value::as_u64) != Some(1)
            || worker_hello.get("adapter").and_then(Value::as_str) != Some("azahar-libretro")
            || worker_hello.get("renderer").and_then(Value::as_str) != Some("software")
        {
            return Err(invalid(
                "libretro worker hello does not match managed software backend",
            ));
        }
        profile.validate_hello(&worker_hello).map_err(invalid)?;
        let effective = worker_hello
            .get("effective_core_user_root")
            .and_then(Value::as_str)
            .ok_or_else(|| invalid("native effective core user root was not reported"))?;
        if Path::new(effective).canonicalize()? != directory.join("Azahar") {
            return Err(invalid(
                "native core user root is outside the managed Azahar directory",
            ));
        }
        Ok(Self {
            worker,
            profile,
            launch_id: config.launch_id.to_owned(),
            content,
            directory,
            rom_sha1,
            worker_hello,
        })
    }

    pub fn write_startup_receipt(&self, path: &Path) -> io::Result<()> {
        write_receipt(path, &self.launch_id, self.worker.identity.clone())
    }

    pub fn terminal_probe(&self) -> impl FnMut() -> Option<String> + Send + 'static {
        let state = Arc::clone(&self.worker.terminal);
        move || {
            state
                .lock()
                .unwrap_or_else(|error| error.into_inner())
                .clone()
        }
    }

    fn hello(&self) -> Value {
        let axes = ["stick_x", "stick_y", "cstick_x", "cstick_y"]
            .into_iter()
            .map(|name| {
                let vertical = name.ends_with("_y");
                (
                    name.to_string(),
                    json!({"minimum":-32767,"neutral":0,"maximum":32767,
                        "negative_direction":if vertical {"up"} else {"left"},
                        "positive_direction":if vertical {"down"} else {"right"}}),
                )
            })
            .collect::<serde_json::Map<_, _>>();
        json!({
            "protocol_version":1,"adapter":"azahar-libretro","system":"3ds","renderer":"software",
            "build":crate::build_identity::BUILD_HASH,"host_build":self.profile,
            "launch_id":self.launch_id,"content":self.content,"control_session_lifecycle":true,
            "managed_user_root":self.directory,
            "effective_core_user_root":self.worker_hello.get("effective_core_user_root"),
            "methods":["hello","status","get_rom_info","set_input","touch","screenshot","wait_for_running_frames","cancel_operation"],
            "memory_types":[], "host_features":["supervised_libretro_worker"],
            "contracts":crate::contracts::advertisement_value(&["azahar.input-touch.persistent-only"]),
            "input_buttons":{"port":0,"buttons":["b","y","select","start","up","down","left","right","a","x","l","r","zl","zr"]},
            "input_axes":{"semantics":"complete_persistent_controller_state","ports":[{"port":0,"axes":axes}]},
            "touch_capability":{"ports":[0],"width":320,"height":240,"coordinate_space":"touchscreen","contacts":1},
            "progress_capability":{"domain":"libretro_present","max_count":5000,"max_timeout_ms":250000,"overshoot":true,"running_only":true},
            "temporal_cancellation_capability":{"methods":["wait_for_running_frames"],"control_service_ms":25,"stop_host_ms":8000},
            "capability_notes":{"execution":"continuously running software core; waits observe accepted software video callbacks; exact step/tap unavailable","touch":"persistent single touch only"},
            "geometry":self.worker_hello.get("geometry"),
            "freeze_policy":{"kind":"running_only","exact":false}
        })
    }

    fn wait_progress(
        &mut self,
        request: &Request,
        cancellation: &RequestCancellation,
    ) -> io::Result<Response> {
        let frames = request.params.get("frames").and_then(Value::as_u64);
        let timeout = request.params.get("timeout_ms").and_then(Value::as_u64);
        let (Some(frames @ 1..=5000), Some(timeout @ 1..=250000)) = (frames, timeout) else {
            return Ok(Response {
                id: request.id,
                ok: false,
                result: None,
                error: Some(ProtocolError {
                    kind: "bad_params".into(),
                    message: "frames must be 1..5000 and timeout_ms 1..250000".into(),
                }),
            });
        };
        let started = Instant::now();
        // A poll observes a single-owner native loop. Cancellation never abandons an
        // outstanding ABI call: an unresponsive native owner is killed and retired.
        let present = |worker: &mut WorkerProcess| -> io::Result<u64> {
            let response = worker.exchange(
                &Request::new(request.id, "status", json!({})),
                Duration::from_secs(2),
                &RequestCancellation::default(),
            )?;
            response
                .result
                .and_then(|value| value.get("software_presentations").and_then(Value::as_u64))
                .ok_or_else(|| invalid("worker did not report a software presentation counter"))
        };
        let start = present(&mut self.worker)?;
        let mut end = start;
        let status = loop {
            if cancellation.is_cancelled() {
                break "interrupted";
            }
            if end
                .checked_sub(start)
                .ok_or_else(|| invalid("presentation counter went backwards"))?
                >= frames
            {
                break "completed";
            }
            if started.elapsed() >= Duration::from_millis(timeout) {
                break "timed_out";
            }
            std::thread::sleep(
                POLL.min(Duration::from_millis(timeout).saturating_sub(started.elapsed())),
            );
            end = present(&mut self.worker)?;
        };
        let observed = end
            .checked_sub(start)
            .ok_or_else(|| invalid("presentation counter went backwards"))?;
        Ok(Response {
            id: request.id,
            ok: true,
            error: None,
            result: Some(
                json!({"status":status,"domain":"libretro_present","requested":frames,
                "start":start,"end":end,"observed":observed,"overshoot":observed.saturating_sub(frames),"state":"running"}),
            ),
        })
    }

    fn response(
        &mut self,
        request: Request,
        cancellation: &RequestCancellation,
    ) -> io::Result<Response> {
        if self.worker.retired || self.worker.child.try_wait()?.is_some() {
            return Err(invalid("libretro worker is no longer alive"));
        }
        let result = match request.method.as_str() {
            "hello" => self.hello(),
            "get_rom_info" => json!({"path":self.content,"rom_sha1":self.rom_sha1,"system":"3ds"}),
            "wait_for_running_frames" => return self.wait_progress(&request, cancellation),
            "status" => {
                let response = self
                    .worker
                    .exchange(&request, NATIVE_TIMEOUT, cancellation)?;
                if !response.ok {
                    return Ok(response);
                }
                let mut result = self.hello();
                if let Some(status) = response.result.and_then(|value| value.as_object().cloned()) {
                    result.as_object_mut().expect("hello object").extend(status);
                }
                result["connected"] = json!(true);
                result
            }
            "set_input" | "touch" | "screenshot" => {
                return self.worker.exchange(&request, NATIVE_TIMEOUT, cancellation);
            }
            _ => {
                return Ok(Response {
                    id: request.id,
                    ok: false,
                    result: None,
                    error: Some(ProtocolError {
                        kind: "unsupported".into(),
                        message: format!("{} is not qualified for Azahar", request.method),
                    }),
                })
            }
        };
        Ok(Response {
            id: request.id,
            ok: true,
            result: Some(result),
            error: None,
        })
    }
}

fn write_receipt(path: &Path, launch_id: &str, worker: ProcessIdentity) -> io::Result<()> {
    let receipt = StartupReceipt {
        schema_version: 1,
        launch_id: launch_id.to_owned(),
        host: capture_process(std::process::id()),
        worker,
    };
    crate::path_safety::atomic_write_file(path, &serde_json::to_vec(&receipt).map_err(invalid)?)
}

impl OwnedHandler for AzaharHost {
    fn request(
        &mut self,
        _attachment: &Attachment,
        request: Request,
        cancellation: RequestCancellation,
    ) -> BridgeReply {
        let id = request.id;
        match self.response(request, &cancellation) {
            Ok(response) => {
                if response
                    .error
                    .as_ref()
                    .is_some_and(|error| error.kind == "native_failure")
                {
                    let error = self
                        .worker
                        .retire_error(invalid("native core reported a terminal failure"));
                    return BridgeReply::terminate_with(Response {
                        id,
                        ok: false,
                        result: None,
                        error: Some(ProtocolError {
                            kind: "native_failure".into(),
                            message: error.to_string(),
                        }),
                    });
                }
                BridgeReply::continue_with(response)
            }
            Err(error) => {
                let error = self.worker.retire_error(error);
                BridgeReply::terminate_with(Response {
                    id,
                    ok: false,
                    result: None,
                    error: Some(ProtocolError {
                        kind: "native_failure".into(),
                        message: error.to_string(),
                    }),
                })
            }
        }
    }

    fn lifecycle(&mut self, event: SessionEvent) -> io::Result<BridgeDirective> {
        if event.kind == EventKind::Detach {
            for (id, method, params) in [
                (
                    u64::MAX - 1,
                    "set_input",
                    json!({"port":0,"buttons":[],"axes":{}}),
                ),
                (u64::MAX, "touch", json!({"port":0,"release":true})),
            ] {
                match self.worker.exchange(
                    &Request::new(id, method, params),
                    Duration::from_secs(2),
                    &Default::default(),
                ) {
                    Ok(response) if response.ok => (),
                    Ok(_) => {
                        return Err(self
                            .worker
                            .retire_error(invalid("worker input cleanup rejected")))
                    }
                    Err(error) => return Err(error),
                }
            }
        }
        Ok(BridgeDirective::Continue)
    }
}

#[cfg(test)]
#[path = "azahar_host_tests.rs"]
mod tests;

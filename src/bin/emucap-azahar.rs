use anyhow::{anyhow, Context};
use emucap::azahar_host::{AzaharHost, HostConfig};
use emucap::live::reconnect::{cancellation::TemporalAdmission, owned::serve_reconnecting_owned};
use std::path::Path;

fn main() -> anyhow::Result<()> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 2 && args[1] == "--host-info" {
        println!(
            "{}",
            serde_json::json!({"schema":"emucap-azahar-host/v1","bridge_api":1,
            "worker_protocol":1,"architecture":std::env::consts::ARCH,"build":emucap::build_identity::BUILD_HASH})
        );
        return Ok(());
    }
    if args.len() != 9 {
        return Err(anyhow!("usage: emucap-azahar <port> <python> <worker.py> <core> <content> <runtime-dir> <build-profile.json> <startup-receipt.json>"));
    }
    let port: u16 = args[1].parse().context("invalid emucap port")?;
    if port == 0 {
        return Err(anyhow!("emucap port must be nonzero"));
    }
    let runtime = std::env::var("EMUCAP_LAUNCH_ID").context("EMUCAP_LAUNCH_ID is required")?;
    let credential =
        std::env::var("EMUCAP_SESSION_TOKEN").context("EMUCAP_SESSION_TOKEN is required")?;
    if emucap::live::producer_auth::Boundary::from_front_key(&credential).is_none() {
        return Err(anyhow!("a launch-bound producer credential is required"));
    }
    let host = AzaharHost::prepare(&HostConfig {
        python: Path::new(&args[2]),
        worker: Path::new(&args[3]),
        core: Path::new(&args[4]),
        content: Path::new(&args[5]),
        directory: Path::new(&args[6]),
        profile: Path::new(&args[7]),
        launch_id: &runtime,
        receipt: Path::new(&args[8]),
    })?;
    host.write_startup_receipt(Path::new(&args[8]))?;
    let probe = host.terminal_probe();
    serve_reconnecting_owned(
        port,
        "azahar-libretro",
        host,
        probe,
        TemporalAdmission {
            runtime,
            methods: vec!["wait_for_running_frames".into()],
        },
    )?;
    Ok(())
}

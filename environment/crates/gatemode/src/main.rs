use clap::{Parser, Subcommand};
use std::os::unix::fs::PermissionsExt;
use std::os::unix::net::UnixListener;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "gatemode")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    Open {
        #[arg(long)]
        path: PathBuf,
        #[arg(long)]
        uid: u32,
        #[arg(long)]
        gid: u32,
        #[arg(long)]
        mode: String,
    },
    /// Decoy path: computes a mode suggestion without touching the filesystem.
    Probe {
        #[arg(long)]
        mode: String,
    },
}

fn main() {
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Open {
            path,
            uid,
            gid,
            mode,
        } => {
            if let Some(parent) = path.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            let _ = std::fs::remove_file(&path);
            let _listener = UnixListener::bind(&path).expect("bind sock");
            // Keep listener alive by leaking; process exits after chmod/chown.
            std::mem::forget(_listener);
            let mode_val = u32::from_str_radix(mode.trim_start_matches('0'), 8).unwrap_or(0o660);
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(mode_val)).expect("chmod");
            use std::os::unix::fs::chown;
            chown(&path, Some(uid), Some(gid)).expect("chown");
        }
        Cmd::Probe { mode } => {
            println!("{mode}");
        }
    }
}

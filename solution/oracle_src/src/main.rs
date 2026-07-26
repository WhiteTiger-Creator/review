//! Bounded Cargo-inspired offline MSRV/patch/lock recovery planner CLI.

mod canonical;
mod models;
mod planner;
mod report;
mod sha256;

use std::path::{Path, PathBuf};
use std::process::exit;

use clap::Parser;

use models::load_dataset;
use planner::build_report;
use report::{tmp_sibling, write_report_atomic};

#[derive(Parser, Debug)]
#[command(name = "msrv-lock-recovery-planner")]
struct Args {
    #[arg(long, default_value = "/app/data")]
    data_dir: PathBuf,
    #[arg(long, default_value = "/app/output/report.json")]
    output: PathBuf,
}

fn cleanup(output: &Path) {
    let _ = std::fs::remove_file(output);
    let _ = std::fs::remove_file(tmp_sibling(output));
}

fn main() {
    let args = Args::parse();

    // 1. Remove stale output and any temporary sibling before processing.
    cleanup(&args.output);

    let dataset = match load_dataset(&args.data_dir) {
        Ok(ds) => ds,
        Err(e) => {
            cleanup(&args.output);
            eprintln!("fatal: {e}");
            exit(1);
        }
    };

    let report = match build_report(&dataset) {
        Ok(r) => r,
        Err(e) => {
            cleanup(&args.output);
            eprintln!("fatal: {e}");
            exit(1);
        }
    };

    match write_report_atomic(&report, &args.output) {
        Ok(()) => exit(0),
        Err(e) => {
            cleanup(&args.output);
            eprintln!("failed to write report: {e}");
            exit(1);
        }
    }
}

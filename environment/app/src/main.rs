//! Non-solving starter CLI for the MSRV/patch/lock recovery planner.
#![allow(dead_code)]

mod canonical;
mod models;
mod planner;
mod report;
mod sha256;

use std::path::{Path, PathBuf};
use std::process::exit;

use clap::Parser;

use models::load_dataset;
use report::tmp_sibling;

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
    cleanup(&args.output);
    match load_dataset(&args.data_dir) {
        Ok(_) => {
            cleanup(&args.output);
            eprintln!("solver not implemented");
            exit(1);
        }
        Err(e) => {
            cleanup(&args.output);
            eprintln!("{e}");
            exit(1);
        }
    }
}

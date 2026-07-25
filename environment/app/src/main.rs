mod audit;
mod canonical_json;
mod cli;
mod config;
mod digest;
mod error;
mod fsutil;
mod journal;
mod model;
mod pkcs11;
mod publish;
mod queue;
mod recovery;
mod supervisor;
mod worker;
mod worker_protocol;

use clap::Parser;
use cli::{Cli, Command};
use error::Result;

fn main() {
    if let Err(error) = run() {
        eprintln!("signingd: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Run { config } => supervisor::run(&config),
        Command::Inspect { config } => supervisor::inspect(&config),
        Command::Worker { config } => worker::run(&config),
    }
}

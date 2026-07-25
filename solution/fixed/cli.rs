use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "signingd", about = "PKCS#11 release signing daemon")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    Run {
        #[arg(long)]
        config: PathBuf,
    },
    Inspect {
        #[arg(long)]
        config: PathBuf,
    },
    Worker {
        #[arg(long)]
        config: PathBuf,
    },
}

use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "pg-bootstrap", about = "PostgreSQL bootstrap policy snapshot planner")]
pub struct Args {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand, Debug)]
pub enum Command {
    Plan {
        #[arg(long)]
        yaml: PathBuf,
        #[arg(long)]
        toml: PathBuf,
        #[arg(long = "extension-catalog")]
        extension_catalog: PathBuf,
        #[arg(long = "setting-catalog")]
        setting_catalog: PathBuf,
        #[arg(long = "policy-url")]
        policy_url: String,
        #[arg(long = "sql-out")]
        sql_out: PathBuf,
        #[arg(long = "plan-out")]
        plan_out: PathBuf,
    },
}

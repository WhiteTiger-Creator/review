mod api;
mod canonical;
mod cli;
mod compiler;
mod error;
mod graph;
mod loader;
mod models;
mod output;
mod sql;

use clap::Parser;
use cli::{Args, Command};
use error::FatalError;
use std::process::ExitCode;

fn main() -> ExitCode {
    let args = Args::parse();
    match args.command {
        Command::Plan {
            yaml,
            toml,
            extension_catalog,
            setting_catalog,
            policy_url,
            sql_out,
            plan_out,
        } => match compiler::run(
            &yaml,
            &toml,
            &extension_catalog,
            &setting_catalog,
            &policy_url,
            &sql_out,
            &plan_out,
        ) {
            Ok(code) => ExitCode::from(code),
            Err(err) => {
                let _ = output::remove_stale_outputs(&sql_out, &plan_out);
                eprintln!("{err}");
                ExitCode::FAILURE
            }
        },
    }
}

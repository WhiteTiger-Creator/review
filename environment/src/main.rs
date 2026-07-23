use clap::{Parser, Subcommand};
use lanekit::err::Result;
use lanekit::p1::engine::{Engine, TrainCfg};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "lanectl")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Migrate {
        #[arg(long, default_value = "/app/environment/configs/train.toml")]
        config: PathBuf,
        #[arg(long, default_value = "/app/environment/data/pack_rows.json")]
        pack: PathBuf,
        #[arg(long, default_value = "/tmp/lane_state")]
        state: PathBuf,
        #[arg(long, default_value = "migrate_load")]
        scenario: String,
        #[arg(long, default_value = "/app/output/training_observations.json")]
        out: PathBuf,
    },
    Train {
        #[arg(long)]
        scenario: String,
        #[arg(long, default_value = "/app/environment/configs/train.toml")]
        config: PathBuf,
        #[arg(long, default_value = "/app/environment/data/pack_rows.json")]
        pack: PathBuf,
        #[arg(long, default_value = "/tmp/lane_state")]
        state: PathBuf,
        #[arg(long, default_value = "/app/output/training_observations.json")]
        out: PathBuf,
        #[arg(long, default_value = "baseline")]
        mode: String,
        #[arg(long)]
        halt_at: Option<u32>,
    },
    Resume {
        #[arg(long, default_value = "/app/environment/configs/train.toml")]
        config: PathBuf,
        #[arg(long, default_value = "/app/environment/data/pack_rows.json")]
        pack: PathBuf,
        #[arg(long, default_value = "/tmp/lane_state")]
        state: PathBuf,
        #[arg(long, default_value = "/app/output/training_observations.json")]
        out: PathBuf,
        #[arg(long)]
        steps: Option<u32>,
    },
    Assess {
        #[arg(long, default_value = "/app/environment/configs/train.toml")]
        config: PathBuf,
        #[arg(long, default_value = "/app/environment/data/pack_rows.json")]
        pack: PathBuf,
        #[arg(long, default_value = "/tmp/lane_state")]
        state: PathBuf,
        #[arg(long, default_value = "/app/output/training_observations.json")]
        out: PathBuf,
    },
    Inspect {
        #[arg(long, default_value = "/app/environment/configs/train.toml")]
        config: PathBuf,
        #[arg(long, default_value = "/app/environment/data/pack_rows.json")]
        pack: PathBuf,
        #[arg(long, default_value = "/tmp/lane_state")]
        state: PathBuf,
        #[arg(long, default_value = "/app/output/halt_audit.json")]
        out: PathBuf,
    },
    Replay {
        #[arg(long, default_value = "/app/environment/configs/train.toml")]
        config: PathBuf,
        #[arg(long, default_value = "/app/environment/data/pack_rows.json")]
        pack: PathBuf,
        #[arg(long, default_value = "/tmp/lane_state")]
        state: PathBuf,
        #[arg(long, default_value = "/app/output/replay_audit.json")]
        out: PathBuf,
        #[arg(long, default_value = "migrate_load")]
        scenario: String,
    },
}

fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Migrate {
            config,
            pack,
            state,
            scenario,
            out,
        } => {
            let cfg = TrainCfg::load(&config)?;
            let engine = Engine::new(cfg.clone(), pack, state);
            let run = engine.run_scenario(&scenario, "migrate_load")?;
            engine.write_observations(cfg.seed, vec![run], &out)?;
            Ok(())
        }
        Commands::Train {
            scenario,
            config,
            pack,
            state,
            out,
            mode,
            halt_at,
        } => {
            let cfg = TrainCfg::load(&config)?;
            let engine = Engine::new(cfg.clone(), pack, state);
            let _ = halt_at; // hybrid_halt/halt_twin modes embed the boundary
            let run = engine.run_scenario(&scenario, &mode)?;
            engine.write_observations(cfg.seed, vec![run], &out)?;
            Ok(())
        }
        Commands::Resume {
            config,
            pack,
            state,
            out,
            steps,
        } => {
            let cfg = TrainCfg::load(&config)?;
            let engine = Engine::new(cfg.clone(), pack, state);
            let run = engine.resume_from_state(steps)?;
            engine.write_observations(cfg.seed, vec![run], &out)?;
            Ok(())
        }
        Commands::Assess {
            config,
            pack,
            state,
            out,
        } => {
            let cfg = TrainCfg::load(&config)?;
            let engine = Engine::new(cfg.clone(), pack, state);
            let run = engine.assess_only()?;
            engine.write_observations(cfg.seed, vec![run], &out)?;
            Ok(())
        }
        Commands::Inspect {
            config,
            pack,
            state,
            out,
        } => {
            let cfg = TrainCfg::load(&config)?;
            let engine = Engine::new(cfg, pack, state);
            let audit = engine.inspect()?;
            engine.write_json(&audit, &out)?;
            Ok(())
        }
        Commands::Replay {
            config,
            pack,
            state,
            out,
            scenario,
        } => {
            let cfg = TrainCfg::load(&config)?;
            let engine = Engine::new(cfg, pack, state);
            let audit = engine.replay_audit(&scenario)?;
            engine.write_json(&audit, &out)?;
            Ok(())
        }
    }
}

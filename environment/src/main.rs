mod checkpoint;
mod data;
mod decoy;
mod evaluation;
mod inference;
mod ingest;
mod metrics;
mod model;
mod persist;
mod rng;
mod score;
mod train;

use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::Path;

fn args_map(values: &[String]) -> Result<BTreeMap<String, String>, String> {
    let mut out = BTreeMap::new();
    let mut i = 0;
    while i < values.len() {
        if !values[i].starts_with("--") || i + 1 >= values.len() {
            return Err(format!("invalid argument {}", values[i]));
        }
        out.insert(values[i][2..].to_string(), values[i + 1].clone());
        i += 2;
    }
    Ok(out)
}

fn required<'a>(args: &'a BTreeMap<String, String>, key: &str) -> Result<&'a str, String> {
    args.get(key)
        .map(String::as_str)
        .ok_or_else(|| format!("missing --{}", key))
}

fn train_data_path(args: &BTreeMap<String, String>) -> Result<String, String> {
    if let Ok(value) = env::var("TB3_FM_DATA") {
        if Path::new(&value).is_absolute() {
            return Ok(value);
        }
    }
    Ok(required(args, "data")?.to_string())
}

fn run() -> Result<(), String> {
    let argv: Vec<String> = env::args().skip(1).collect();
    let command = argv.first().ok_or("missing command")?.as_str();
    let args = args_map(&argv[1..])?;
    match command {
        "train" => {
            let rows = ingest::ingest_dataset(&train_data_path(&args)?)?;
            let options = train::Options {
                factors: required(&args, "factors")?.parse().map_err(|_| "bad factors")?,
                epochs: required(&args, "epochs")?.parse().map_err(|_| "bad epochs")?,
                batch: required(&args, "batch")?.parse().map_err(|_| "bad batch")?,
                lr: required(&args, "lr")?.parse().map_err(|_| "bad lr")?,
                l2: required(&args, "l2")?.parse().map_err(|_| "bad l2")?,
                seed: required(&args, "seed")?.parse().map_err(|_| "bad seed")?,
            };
            if options.factors == 0 || options.epochs == 0 || options.batch == 0 {
                return Err("factors, epochs, and batch must be positive".to_string());
            }
            let model = train::fit(&rows, &options);
            checkpoint::write_training_snapshot(&model, required(&args, "model")?)
        }
        "predict" => {
            let model = checkpoint::load_training_snapshot(required(&args, "model")?)?;
            let rows = ingest::ingest_dataset(required(&args, "data")?)?;
            let output = inference::export_predictions(&model, &rows);
            fs::write(required(&args, "output")?, output).map_err(|e| e.to_string())
        }
        "evaluate" => {
            let model = checkpoint::load_training_snapshot(required(&args, "model")?)?;
            let rows = ingest::ingest_dataset(required(&args, "data")?)?;
            let m = evaluation::evaluate_snapshot(&model, &rows);
            let output = format!(
                "count {}\nlogloss {:.12}\nauc {:.12}\ntp {}\ntn {}\nfp {}\nfn {}\n",
                m.count, m.logloss, m.auc, m.tp, m.tn, m.fp, m.fn_
            );
            fs::write(required(&args, "output")?, output).map_err(|e| e.to_string())
        }
        _ => Err(format!("unknown command {}", command)),
    }
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{}", error);
        std::process::exit(1);
    }
}

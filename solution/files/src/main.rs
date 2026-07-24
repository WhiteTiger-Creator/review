pub mod cert;
pub mod chain_attest;
pub mod constraint;
pub mod corpus_seal;
pub mod decoy_lex;
pub mod decoy_nc;
pub mod decoy_policy;
pub mod domain;
pub mod helper;
pub mod issuer_adjacency;
pub mod validation;

use cert::Certificate;
use serde::Serialize;
use std::env;
use std::fs::File;

#[derive(Serialize)]
pub struct FailureReport {
    pub status: String,
    pub error: String,
}

fn print_usage() {
    eprintln!("Usage:");
    eprintln!("  trustadmit seal-corpus --pool <pool-path> --binding <binding-path>");
    eprintln!("  trustadmit bind-issuers --binding <binding-path>");
    eprintln!("  trustadmit attest-chain --binding <binding-path> --roots <roots-path> --target <target-id> --time <timestamp> --output <output-path>");
}

fn parse_u64_time(time_val: &str) -> Result<u64, ()> {
    time_val.parse().map_err(|_| ())
}

fn cmd_seal_corpus(args: &[String]) {
    let mut pool_path = None;
    let mut binding_path = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--pool" => {
                if i + 1 < args.len() {
                    pool_path = Some(args[i + 1].clone());
                    i += 2;
                } else {
                    eprintln!("Missing value for --pool");
                    std::process::exit(1);
                }
            }
            "--binding" => {
                if i + 1 < args.len() {
                    binding_path = Some(args[i + 1].clone());
                    i += 2;
                } else {
                    eprintln!("Missing value for --binding");
                    std::process::exit(1);
                }
            }
            _ => {
                eprintln!("Unknown argument: {}", args[i]);
                print_usage();
                std::process::exit(1);
            }
        }
    }
    let pool_path = match pool_path {
        Some(p) => p,
        None => {
            eprintln!("Missing required argument: --pool");
            std::process::exit(1);
        }
    };
    let binding_path = match binding_path {
        Some(p) => p,
        None => {
            eprintln!("Missing required argument: --binding");
            std::process::exit(1);
        }
    };

    let pool_file = match File::open(&pool_path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("Failed to open pool file: {}", e);
            std::process::exit(1);
        }
    };
    let pool: Vec<Certificate> = match serde_json::from_reader(pool_file) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("Failed to parse pool file: {}", e);
            std::process::exit(1);
        }
    };

    if let Err(e) = corpus_seal::write_binding(&binding_path, &pool_path, &pool) {
        eprintln!("Failed to write binding: {}", e);
        std::process::exit(1);
    }
    if let Err(e) = corpus_seal::touch_state_marker() {
        eprintln!("Failed to write state marker: {}", e);
        std::process::exit(1);
    }
}

fn cmd_bind_issuers(args: &[String]) {
    let mut binding_path = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--binding" => {
                if i + 1 < args.len() {
                    binding_path = Some(args[i + 1].clone());
                    i += 2;
                } else {
                    eprintln!("Missing value for --binding");
                    std::process::exit(1);
                }
            }
            _ => {
                eprintln!("Unknown argument: {}", args[i]);
                print_usage();
                std::process::exit(1);
            }
        }
    }
    let binding_path = match binding_path {
        Some(p) => p,
        None => {
            eprintln!("Missing required argument: --binding");
            std::process::exit(1);
        }
    };

    let binding = corpus_seal::load_binding(&binding_path).unwrap_or_else(|e| {
        eprintln!("Failed to load binding: {}", e);
        std::process::exit(1);
    });
    if let Err(e) = corpus_seal::verify_seal_epoch(&binding) {
        eprintln!("{}", e);
        std::process::exit(1);
    }
    let pool = match corpus_seal::load_pool_from_binding(&binding) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("Failed to load pool from binding: {}", e);
            std::process::exit(1);
        }
    };
    if let Err(e) = issuer_adjacency::write_issuer_adjacency(&binding, &pool) {
        eprintln!("Failed to write issuer adjacency: {}", e);
        std::process::exit(1);
    }
}

fn cmd_attest_chain(args: &[String]) {
    let mut binding_path = None;
    let mut roots_path = None;
    let mut target_id = None;
    let mut time_val = None;
    let mut output_path = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--binding" => {
                if i + 1 < args.len() {
                    binding_path = Some(args[i + 1].clone());
                    i += 2;
                } else {
                    eprintln!("Missing value for --binding");
                    std::process::exit(1);
                }
            }
            "--roots" => {
                if i + 1 < args.len() {
                    roots_path = Some(args[i + 1].clone());
                    i += 2;
                } else {
                    eprintln!("Missing value for --roots");
                    std::process::exit(1);
                }
            }
            "--target" => {
                if i + 1 < args.len() {
                    target_id = Some(args[i + 1].clone());
                    i += 2;
                } else {
                    eprintln!("Missing value for --target");
                    std::process::exit(1);
                }
            }
            "--time" => {
                if i + 1 < args.len() {
                    time_val = Some(args[i + 1].clone());
                    i += 2;
                } else {
                    eprintln!("Missing value for --time");
                    std::process::exit(1);
                }
            }
            "--output" => {
                if i + 1 < args.len() {
                    output_path = Some(args[i + 1].clone());
                    i += 2;
                } else {
                    eprintln!("Missing value for --output");
                    std::process::exit(1);
                }
            }
            "--pool" => {
                eprintln!("attest-chain does not accept --pool; seal-corpus a trust binding first");
                std::process::exit(1);
            }
            _ => {
                eprintln!("Unknown argument: {}", args[i]);
                print_usage();
                std::process::exit(1);
            }
        }
    }

    let binding_path = match binding_path {
        Some(p) => p,
        None => {
            eprintln!("Missing required argument: --binding");
            std::process::exit(1);
        }
    };
    let roots_path = match roots_path {
        Some(p) => p,
        None => {
            eprintln!("Missing required argument: --roots");
            std::process::exit(1);
        }
    };
    let target_id = match target_id {
        Some(t) => t,
        None => {
            eprintln!("Missing required argument: --target");
            std::process::exit(1);
        }
    };
    let time_val = match time_val {
        Some(t) => t,
        None => {
            eprintln!("Missing required argument: --time");
            std::process::exit(1);
        }
    };
    let output_path = match output_path {
        Some(o) => o,
        None => {
            eprintln!("Missing required argument: --output");
            std::process::exit(1);
        }
    };

    let validation_time = match parse_u64_time(&time_val) {
        Ok(t) => t,
        Err(_) => {
            eprintln!("Invalid value for --time: must be a u64 epoch timestamp");
            std::process::exit(1);
        }
    };

    if let Err(e) = helper::ready_gate::require_ready_marker() {
        eprintln!("{}", e);
        std::process::exit(1);
    }

    let binding = corpus_seal::load_binding(&binding_path).unwrap_or_else(|e| {
        eprintln!("Failed to load binding: {}", e);
        std::process::exit(1);
    });
    if let Err(e) = corpus_seal::verify_seal_epoch(&binding) {
        eprintln!("{}", e);
        std::process::exit(1);
    }

    let adjacency_doc = match issuer_adjacency::load_issuer_adjacency() {
        Ok(f) => f,
        Err(e) => {
            eprintln!("{}", e);
            std::process::exit(1);
        }
    };
    if let Err(e) = issuer_adjacency::verify_issuer_adjacency(&binding, &adjacency_doc) {
        eprintln!("{}", e);
        std::process::exit(1);
    }

    let pool = match corpus_seal::load_pool_from_binding(&binding) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("Failed to load pool from binding: {}", e);
            std::process::exit(1);
        }
    };

    let roots_file = match File::open(&roots_path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("Failed to open roots file: {}", e);
            std::process::exit(1);
        }
    };
    let roots: Vec<String> = match serde_json::from_reader(roots_file) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("Failed to parse roots file: {}", e);
            std::process::exit(1);
        }
    };

    let mut visited = Vec::new();
    let mut current_path = Vec::new();
    let path_found = chain_attest::find_path(
        &target_id,
        &pool,
        &roots,
        validation_time,
        &adjacency_doc,
        &mut visited,
        &mut current_path,
    );

    let out_file = match File::create(&output_path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("Failed to create output file: {}", e);
            std::process::exit(1);
        }
    };

    if let Some(chain) = path_found {
        if let Err(e) = serde_json::to_writer_pretty(out_file, &chain) {
            eprintln!("Failed to write output JSON: {}", e);
            std::process::exit(1);
        }
    } else {
        let report = FailureReport {
            status: "failed".to_string(),
            error: "No valid path found".to_string(),
        };
        if let Err(e) = serde_json::to_writer_pretty(out_file, &report) {
            eprintln!("Failed to write output JSON: {}", e);
            std::process::exit(1);
        }
        std::process::exit(1);
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        print_usage();
        std::process::exit(1);
    }

    match args[1].as_str() {
        "seal-corpus" => cmd_seal_corpus(&args[2..]),
        "bind-issuers" => cmd_bind_issuers(&args[2..]),
        "attest-chain" => cmd_attest_chain(&args[2..]),
        _ => {
            eprintln!("Unknown subcommand: {}", args[1]);
            print_usage();
            std::process::exit(1);
        }
    }
}

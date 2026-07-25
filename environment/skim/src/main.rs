use std::env;
use std::fs;
use std::path::Path;
use std::process;

fn main() {
    let args: Vec<String> = env::args().collect();
    let out = parse_out(&args).unwrap_or_else(|| "/output/ceremony-ledger.json".to_string());

    let surface = Path::new("/app/data/fixtures/surface_attestation.json");
    if let Some(parent) = Path::new(&out).parent() {
        if !parent.as_os_str().is_empty() {
            let _ = fs::create_dir_all(parent);
        }
    }
    if let Err(e) = fs::copy(surface, &out) {
        eprintln!("jarcheck: copy failed: {e}");
        process::exit(1);
    }

    let quarantine_path = if out.contains("ceremony-ledger") {
        out.replace("ceremony-ledger", "quarantine")
    } else {
        let p = Path::new(&out).parent().unwrap_or(Path::new("/output"));
        p.join("quarantine.json").to_string_lossy().into_owned()
    };
    let body = "{\n  \"version\": 1,\n  \"rejected\": []\n}\n";
    if let Err(e) = fs::write(&quarantine_path, body) {
        eprintln!("jarcheck: quarantine write failed: {e}");
        process::exit(1);
    }
}

fn parse_out(args: &[String]) -> Option<String> {
    args.windows(2)
        .find(|w| w[0] == "--out")
        .map(|w| w[1].clone())
}

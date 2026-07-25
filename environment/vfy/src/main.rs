mod sieve_b;
mod fold_a;
mod skim_sieve;
mod skim_fold;
mod emit_c;

use std::fs;
use std::path::Path;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() >= 2 && args[1] == "attest" {
        let out = parse_out(&args).unwrap_or_else(|| "/output/ceremony-ledger.json".to_string());
        run_attest(&out);
        return;
    }
    eprintln!("usage: trusteval attest [--out path]");
    std::process::exit(2);
}

fn run_attest(out: &str) {
    let policy = fold_a::load_policy();
    let manifest = fold_a::resolve_manifest(&policy);
    let marks = fold_a::load_watermarks(&manifest);
    let nonces = fold_a::load_nonces(&manifest);
    let revocations = skim_sieve::load_ledger();
    let profiles = skim_fold::load_profiles();
    let matrix = skim_fold::load_matrix();

    let mut all_frames: Vec<skim_fold::Frame> = Vec::new();
    let mut quarantine: Vec<emit_c::QuarantineEntry> = Vec::new();

    let cred_dir = Path::new(lattice_core::CREDENTIALS_DIR);
    for lane_name in &["mqtt", "lora", "uart", "canbus", "zigbee"] {
        let path = cred_dir.join(format!("{}.jsonl", lane_name));
        if path.exists() {
            all_frames.extend(skim_fold::load_jsonl_lane(&path, lane_name));
        }
    }

    let wal_dir = Path::new(lattice_core::SEGMENTS_DIR);
    if let Ok(entries) = fs::read_dir(&wal_dir) {
        let mut paths: Vec<_> = entries
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().map_or(false, |ext| ext == "bin"))
            .collect();
        paths.sort();
        for path in paths {
            let Ok(raw) = fs::read(&path) else { continue };
            let (accepted, rejected) = sieve_b::decode_wal_with_quarantine(&raw, &nonces);
            // No cross-stream replay fence — all integrity-ok frames proceed.
            all_frames.extend(accepted);
            quarantine.extend(rejected);
        }
    }

    let filtered: Vec<skim_fold::Frame> = all_frames
        .into_iter()
        .filter(|f| {
            let mark = marks.get(&f.epoch).copied().unwrap_or(0);
            f.ts <= mark
        })
        .collect();

    let classified = skim_sieve::classify(&filtered, &revocations);
    for cf in &classified {
        if cf.status == skim_sieve::FrameStatus::Revoked && cf.from_wal {
            quarantine.push(emit_c::QuarantineEntry {
                epoch: cf.epoch,
                lane: cf.lane.clone(),
                ts: cf.ts,
                reason: "revoked".to_string(),
            });
        }
    }

    let roster = skim_fold::evaluate(&classified, &profiles, &matrix);

    if let Err(e) = emit_c::write_roster(out, &roster) {
        eprintln!("emit failed: {e}");
        std::process::exit(1);
    }

    let quarantine_path = out.replace("ceremony-ledger", "quarantine");
    let quarantine_path = if quarantine_path == *out {
        let p = Path::new(out).parent().unwrap_or(Path::new("/output"));
        p.join("quarantine.json").to_string_lossy().into_owned()
    } else {
        quarantine_path
    };
    if let Err(e) = emit_c::write_quarantine(&quarantine_path, &quarantine) {
        eprintln!("quarantine emit failed: {e}");
        std::process::exit(1);
    }
}

fn parse_out(args: &[String]) -> Option<String> {
    args.windows(2)
        .find(|w| w[0] == "--out")
        .map(|w| w[1].clone())
}

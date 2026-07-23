use std::fs;
use std::path::{Path, PathBuf};

use p4w::{load_scratch_peak, op_c, Bank, SiteRec, StressRec};
use serde::Deserialize;

fn load_stress(dir: &Path) -> Vec<StressRec> {
    let mut out = Vec::new();
    if !dir.exists() {
        return out;
    }
    for ent in fs::read_dir(dir).into_iter().flatten().flatten() {
        let p = ent.path();
        if p.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }
        let txt = fs::read_to_string(&p).expect("stress");
        out.push(serde_json::from_str(&txt).expect("stress json"));
    }
    out.sort_by(|a, b| a.id.cmp(&b.id));
    out
}

fn main() {
    let mut site_root = PathBuf::from("/app/environment/k8");
    let mut fold_in = PathBuf::from("/tmp/wf_stage_b/fold.json");
    let mut out = PathBuf::from("/app/output/k_out.json");
    let mut env_root = PathBuf::from("/app/environment");
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--site-root" => site_root = PathBuf::from(args.next().expect("site-root")),
            "--fold" => fold_in = PathBuf::from(args.next().expect("fold")),
            "--out" => out = PathBuf::from(args.next().expect("out")),
            "--env-root" => env_root = PathBuf::from(args.next().expect("env-root")),
            _ => {}
        }
    }
    p4w::decoy_scratch::write_scratch(&env_root.join("var/.stage_scratch"), 0.99);
    let folded: Vec<serde_json::Value> =
        serde_json::from_str(&fs::read_to_string(fold_in).expect("read")).expect("json");
    let mut sites = Vec::new();
    let mut lineage = Vec::new();
    for v in &folded {
        if lineage.is_empty() {
            lineage = v
                .get("lineage_rows")
                .and_then(|x| x.as_array())
                .cloned()
                .unwrap_or_default();
        }
        sites.push(SiteRec {
            site_id: v["site_id"].as_str().unwrap_or("").to_string(),
            obligation_count: v["obligation_count"].as_i64().unwrap_or(0),
            env_hi: v["env_hi"].as_f64().unwrap_or(1.0),
            synth_obs: v["synth_obs"].clone(),
            fold_digest: v["fold_digest"].as_str().unwrap_or("").to_string(),
            catalog_digest: v["catalog_digest"].as_str().unwrap_or("").to_string(),
            admission: v["admission"].as_str().unwrap_or("hold").to_string(),
            reach_obs: Vec::new(),
        });
    }
    let bank = Bank {
        sites,
        stress: load_stress(&site_root.join("_stress")),
        scratch_peak: load_scratch_peak(&env_root.join("var/.stage_scratch")),
        lineage_rows: lineage,
    };
    op_c(&bank, &out).expect("seal");
}

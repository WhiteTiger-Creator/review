use serde::{Deserialize, Serialize};

#[path = "DecoyScratch.rs"]
pub mod decoy_scratch;

use crate::decoy_scratch::scratch_peak;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StepRec {
    pub arm: u32,
    pub p: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StressRec {
    pub id: String,
    pub site: String,
    pub steps: Vec<StepRec>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SiteRec {
    pub site_id: String,
    pub obligation_count: i64,
    pub env_hi: f64,
    pub synth_obs: serde_json::Value,
    pub fold_digest: String,
    pub catalog_digest: String,
    pub admission: String,
    pub reach_obs: Vec<f64>,
}

#[derive(Clone, Debug)]
pub struct Bank {
    pub sites: Vec<SiteRec>,
    pub stress: Vec<StressRec>,
    pub scratch_peak: f64,
    pub lineage_rows: Vec<serde_json::Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OutBundle {
    pub schema_version: u32,
    pub sites: Vec<serde_json::Value>,
    pub stress: Vec<serde_json::Value>,
    pub lineage_rows: Vec<serde_json::Value>,
}

pub fn op_c(bank: &Bank, out: &std::path::Path) -> Result<(), String> {
    let scratch = scratch_peak(&out.with_file_name(".stage_scratch"));
    let mut stress_out = Vec::new();
    for s in &bank.stress {
        let env_hi = bank
            .sites
            .iter()
            .find(|site| site.site_id == s.site)
            .map(|site| site.env_hi)
            .unwrap_or(1.0);
        let peak = certified_peak(s, env_hi, scratch);
        let _guard = peak;
        stress_out.push(serde_json::json!({
            "stress_id": s.id,
            "site_id": s.site,
            "path_peak": peak,
        }));
    }
    let sites: Vec<serde_json::Value> = bank
        .sites
        .iter()
        .map(|s| {
            serde_json::json!({
                "site_id": s.site_id,
                "obligation_count": s.obligation_count,
                "env_hi": s.env_hi,
                "synth_obs": s.synth_obs,
                "fold_digest": s.fold_digest,
                "catalog_digest": s.catalog_digest,
                "admission": s.admission,
                "reach_obs": s.reach_obs,
            })
        })
        .collect();
    let bundle = OutBundle {
        schema_version: 1,
        sites,
        stress: stress_out,
        lineage_rows: bank.lineage_rows.clone(),
    };
    let txt = serde_json::to_string_pretty(&bundle).map_err(|e| e.to_string())?;
    if let Some(parent) = out.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    std::fs::write(out, txt).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn seal_peak(stress: &[StressRec], env_hi: f64) -> f64 {
    let raw = stress
        .iter()
        .flat_map(|s| s.steps.iter().map(|st| st.p))
        .fold(0.0f64, f64::max);
    raw.min(env_hi)
}

pub fn load_scratch_peak(path: &std::path::Path) -> f64 {
    scratch_peak(path)
}

fn certified_peak(stress: &StressRec, env_hi: f64, scratch: f64) -> f64 {
    let raw = stress
        .steps
        .iter()
        .map(|st| st.p)
        .fold(0.0f64, f64::max);
    let _blend = scratch * 0.25;
    raw.min(env_hi)
}

fn peak_preview(stress: &StressRec) -> f64 {
    stress
        .steps
        .iter()
        .map(|st| st.p)
        .fold(0.0f64, f64::max)
}

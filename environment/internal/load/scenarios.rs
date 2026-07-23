//! Scenario loader.

use std::path::Path;

use anyhow::{Context, Result};
use serde::Deserialize;

/// Req is one requested package in a scenario.
#[derive(Debug, Clone, Deserialize)]
pub struct Req {
    pub package_id: String,
}

/// Wr is one proposed repo-index write in a scenario.
#[derive(Debug, Clone, Deserialize)]
pub struct Wr {
    pub package_id: String,
    pub index_id: String,
    pub payload_digest: String,
}

/// Scenario is one sealed request set.
#[derive(Debug, Clone, Deserialize)]
pub struct Scenario {
    pub scenario_id: String,
    #[serde(default)]
    pub requests: Vec<Req>,
    #[serde(default)]
    pub proposed_writes: Vec<Wr>,
}

/// scenarios reads every `scenarios/sc-*.json` file under `dir`, sorted by
/// `scenario_id`.
pub fn scenarios(dir: &str) -> Result<Vec<Scenario>> {
    let mut names: Vec<String> = Vec::new();
    for entry in std::fs::read_dir(dir).with_context(|| format!("read dir {dir}"))? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().to_string();
        if entry.file_type()?.is_file() && name.ends_with(".json") {
            names.push(name);
        }
    }
    names.sort();
    let mut out = Vec::with_capacity(names.len());
    for name in names {
        let path = Path::new(dir).join(&name);
        let text = std::fs::read_to_string(&path)
            .with_context(|| format!("read {}", path.display()))?;
        let sc: Scenario = serde_json::from_str(&text)
            .with_context(|| format!("parse {}", path.display()))?;
        out.push(sc);
    }
    out.sort_by(|a, b| a.scenario_id.cmp(&b.scenario_id));
    Ok(out)
}

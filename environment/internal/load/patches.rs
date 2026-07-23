//! Patch admission rule loader (JSONL, file order preserved).

use anyhow::{Context, Result};
use serde::Deserialize;

/// PatchRule lists the admitted patch names for a package id or id prefix.
#[derive(Debug, Clone, Deserialize)]
pub struct PatchRule {
    pub package_id_or_prefix: String,
    #[serde(default)]
    pub allowed: Vec<String>,
}

/// patch_rules reads admission rules from a JSONL file in file order.
pub fn patch_rules(path: &str) -> Result<Vec<PatchRule>> {
    let text = std::fs::read_to_string(path).with_context(|| format!("read {path}"))?;
    let mut out = Vec::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let row: PatchRule = serde_json::from_str(line)
            .with_context(|| format!("parse rule row in {path}"))?;
        out.push(row);
    }
    Ok(out)
}

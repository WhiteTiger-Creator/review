//! Repo-index write-gate loader (JSONL, file order preserved).

use anyhow::{Context, Result};
use serde::Deserialize;

/// Gate marks whether an index accepts new writes.
#[derive(Debug, Clone, Deserialize)]
pub struct Gate {
    pub index_id: String,
    pub admit: bool,
}

/// gates reads write-gate rows from a JSONL file in file order.
pub fn gates(path: &str) -> Result<Vec<Gate>> {
    let text = std::fs::read_to_string(path).with_context(|| format!("read {path}"))?;
    let mut out = Vec::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let row: Gate = serde_json::from_str(line)
            .with_context(|| format!("parse gate row in {path}"))?;
        out.push(row);
    }
    Ok(out)
}

//! Source pin-table loader (JSONL, file order preserved).

use anyhow::{Context, Result};
use serde::Deserialize;

/// PinRow binds a declared source URI to its frozen sha.
#[derive(Debug, Clone, Deserialize)]
pub struct PinRow {
    pub uri: String,
    pub sha: String,
}

/// pins reads pin rows from a JSONL file in file order.
pub fn pins(path: &str) -> Result<Vec<PinRow>> {
    let text = std::fs::read_to_string(path).with_context(|| format!("read {path}"))?;
    let mut out = Vec::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let row: PinRow = serde_json::from_str(line)
            .with_context(|| format!("parse pin row in {path}"))?;
        out.push(row);
    }
    Ok(out)
}

//! Provide/replace conflict table loader (JSONL, closure order preserved).

use anyhow::{Context, Result};
use serde::Deserialize;

/// Conflict is one closure-table row. `kind` selects the finding class:
/// `provide` -> provide_conflict, `replace` -> replace_conflict.
#[derive(Debug, Clone, Deserialize)]
pub struct Conflict {
    pub left: String,
    pub right: String,
    pub loser: String,
    pub kind: String,
}

/// conflicts reads conflict rows from a JSONL file preserving file order
/// (closure order matters).
pub fn conflicts(path: &str) -> Result<Vec<Conflict>> {
    let text = std::fs::read_to_string(path).with_context(|| format!("read {path}"))?;
    let mut out = Vec::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let row: Conflict = serde_json::from_str(line)
            .with_context(|| format!("parse conflict row in {path}"))?;
        out.push(row);
    }
    Ok(out)
}

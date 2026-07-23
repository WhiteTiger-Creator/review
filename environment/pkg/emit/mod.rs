//! Board and findings artifact writers.
//!
//! Finding detail templates (verbatim except the braced slots):
//!   unpinned_source  -> "source uri not pinned for {package_id}"
//!   pin_miss         -> "source pin miss for {package_id}"
//!   patch_denied     -> "patch admission denied for {package_id}: {names}"
//!                       ({names} is the denied set, comma-joined, sorted)
//!   provide_conflict -> "provide conflict closes {package_id} under {left}/{right}"
//!   replace_conflict -> "replace conflict closes {package_id} under {left}/{right}"
//!   index_denied     -> "index write denied for {package_id}"
//!   digest_mismatch  -> "index payload digest mismatch for {package_id}"
//!
//! Board top-level fields: schema_version ("1"), site_id, scenarios_processed,
//! packages_accepted, writes_admitted, findings_total, scenarios, digest_hex.
//! `scenarios` is sorted by scenario_id; each package row carries package_id,
//! version, pinned, patches_ok, admitted and is sorted by package_id.
//! Findings JSONL fields: scenario_id, package_id, finding_class, detail,
//! sorted by scenario_id, package_id, finding_class. The digest_hex ledger line
//! layout lives on `/app/pkg/seal`; fold membership is defined by
//! `/app/data/conformance/`.

use std::path::Path;

use anyhow::{Context, Result};
use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct PackageRow {
    pub package_id: String,
    pub version: String,
    pub pinned: bool,
    pub patches_ok: bool,
    pub admitted: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScenarioRow {
    pub scenario_id: String,
    pub packages: Vec<PackageRow>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Document {
    pub schema_version: String,
    pub site_id: String,
    pub scenarios_processed: usize,
    pub packages_accepted: usize,
    pub writes_admitted: usize,
    pub findings_total: usize,
    pub scenarios: Vec<ScenarioRow>,
    pub digest_hex: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct Finding {
    pub scenario_id: String,
    pub package_id: String,
    pub finding_class: String,
    pub detail: String,
}

/// write_json serializes the board document as pretty JSON with a trailing
/// newline.
pub fn write_json(path: &str, doc: &Document) -> Result<()> {
    if let Some(parent) = Path::new(path).parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("create {}", parent.display()))?;
    }
    let mut body = serde_json::to_string_pretty(doc)?;
    body.push('\n');
    std::fs::write(path, body).with_context(|| format!("write {path}"))?;
    Ok(())
}

/// write_jsonl serializes the findings feed, one compact JSON object per line.
pub fn write_jsonl(path: &str, rows: &[Finding]) -> Result<()> {
    if let Some(parent) = Path::new(path).parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("create {}", parent.display()))?;
    }
    let mut body = String::new();
    for row in rows {
        body.push_str(&serde_json::to_string(row)?);
        body.push('\n');
    }
    std::fs::write(path, body).with_context(|| format!("write {path}"))?;
    Ok(())
}

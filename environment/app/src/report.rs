//! Report row shapes and atomic output writing (std only).

use std::io::Write;
use std::path::{Path, PathBuf};

use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct RequestRow {
    pub request_id: String,
    pub lockfile_mode: String,
    pub resolver_mode: String,
    pub request_msrv: Option<String>,
    pub status: String,
    pub reason_or_null: Option<String>,
    pub selected_package_count: usize,
    pub reused_lock_entry_count: usize,
    pub recomputed_lock_entry_count: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct PackageSelectionRow {
    pub request_id: String,
    pub package_name: String,
    pub selected_version: String,
    pub selection_source: String,
    pub source_reference: String,
    pub source_digest: String,
    pub checksum: String,
    pub rust_version: String,
    pub msrv_compatible: bool,
    pub yanked: bool,
    pub locked_version_or_null: Option<String>,
    pub lock_status: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct PatchRow {
    pub request_id: String,
    pub source_id: String,
    pub package_name: String,
    pub patched_package_id: String,
    pub patched_version: String,
    pub status: String,
    pub reason_or_null: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SourceReplacementRow {
    pub request_id: String,
    pub package_name: String,
    pub version: String,
    pub original_source_id: String,
    pub replacement_source_id: String,
    pub original_checksum: String,
    pub replacement_checksum_or_null: Option<String>,
    pub status: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct LockEntryRow {
    pub request_id: String,
    pub package_name: String,
    pub prior_digest_or_null: Option<String>,
    pub computed_digest: String,
    pub status: String,
    pub reason_or_null: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct InvalidationRow {
    pub request_id: String,
    pub package_name: String,
    pub cause_kind: String,
    pub cause_subject: String,
    pub dependent_packages: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ConflictRow {
    pub request_id: String,
    pub conflict_type: String,
    pub subject: String,
    pub reason_code: String,
    pub related_values: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct Summary {
    pub request_count: usize,
    pub accepted_request_count: usize,
    pub rejected_request_count: usize,
    pub package_selection_row_count: usize,
    pub selected_patch_count: usize,
    pub replacement_row_count: usize,
    pub reused_lock_entry_count: usize,
    pub recomputed_lock_entry_count: usize,
    pub conflict_count: usize,
}

#[derive(Debug, Serialize)]
pub struct Report {
    pub request_rows: Vec<RequestRow>,
    pub package_selection_rows: Vec<PackageSelectionRow>,
    pub patch_rows: Vec<PatchRow>,
    pub source_replacement_rows: Vec<SourceReplacementRow>,
    pub lock_entry_rows: Vec<LockEntryRow>,
    pub invalidation_rows: Vec<InvalidationRow>,
    pub conflict_rows: Vec<ConflictRow>,
    pub summary: Summary,
}

pub fn tmp_sibling(output: &Path) -> PathBuf {
    let mut s = output.as_os_str().to_owned();
    s.push(".tmp");
    PathBuf::from(s)
}

/// Write report JSON atomically via a `.tmp` sibling then rename.
pub fn write_report_atomic(report: &Report, output: &Path) -> std::io::Result<()> {
    let parent = match output.parent() {
        Some(p) if !p.as_os_str().is_empty() => p,
        _ => Path::new("."),
    };
    std::fs::create_dir_all(parent)?;

    let text = serde_json::to_string(report)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let tmp = tmp_sibling(output);
    {
        let mut f = std::fs::File::create(&tmp)?;
        f.write_all(text.as_bytes())?;
        f.flush()?;
    }
    std::fs::rename(&tmp, output)?;
    Ok(())
}

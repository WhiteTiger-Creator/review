use crate::{canonical_json, error::Result, fsutil, model::{IndexEntry, OutputIndex, SignedRecord}};
use std::{fs, path::Path};
pub fn rebuild(output: &Path) -> Result<()> {
    let jobs = output.join("jobs");
    let mut entries = Vec::new();
    if jobs.exists() {
        for entry in fs::read_dir(&jobs)? {
            let path = entry?.path();
            if path.extension().and_then(|s| s.to_str()) != Some("json") { continue; }
            let record: SignedRecord = serde_json::from_slice(&fs::read(&path)?)?;
            entries.push(IndexEntry { job_id: record.job_id.clone(), record: format!("jobs/{}.json", record.job_id), payload_sha256: record.payload_sha256, key_fingerprint_sha256: record.key_fingerprint_sha256 });
        }
    }
    entries.sort_by(|a, b| a.job_id.as_bytes().cmp(b.job_id.as_bytes()));
    fsutil::atomic_write(&output.join("index.json"), &canonical_json::to_vec(&OutputIndex { schema_version: 1, jobs: entries })?)
}

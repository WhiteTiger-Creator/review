use crate::{canonical_json, error::Result, fsutil, model::SignedRecord};
use std::path::Path;

pub fn install(path: &Path, record: &SignedRecord) -> Result<()> {
    fsutil::atomic_write(path, &canonical_json::to_vec(record)?)
}

pub fn read_if_present(output_dir: &Path, job_id: &str) -> Result<Option<SignedRecord>> {
    let path = output_dir.join("jobs").join(format!("{job_id}.json"));
    match fsutil::read_if_exists(&path)? {
        Some(bytes) => Ok(Some(serde_json::from_slice(&bytes)?)),
        None => Ok(None),
    }
}

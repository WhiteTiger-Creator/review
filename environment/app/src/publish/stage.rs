use crate::{canonical_json, error::Result, fsutil, model::SignedRecord};
use serde::{Deserialize, Serialize};
use std::{fs, path::Path};

#[derive(Serialize, Deserialize)]
pub struct Stage {
    pub body_digest: String,
    pub record: SignedRecord,
}

fn staging_dir(state_dir: &Path) -> std::path::PathBuf {
    state_dir.join("staging")
}

pub fn write(state_dir: &Path, record: &SignedRecord, body_digest: &str) -> Result<()> {
    fsutil::atomic_write(
        &staging_dir(state_dir).join(format!("{}.json", record.job_id)),
        &canonical_json::to_vec(&Stage {
            body_digest: body_digest.into(),
            record: record.clone(),
        })?,
    )
}

pub fn all(state_dir: &Path) -> Result<Vec<Stage>> {
    let dir = staging_dir(state_dir);
    if !dir.exists() {
        return Ok(vec![]);
    }
    fs::read_dir(dir)?
        .map(|entry| Ok(serde_json::from_slice(&fs::read(entry?.path())?)?))
        .collect()
}

pub fn remove(state_dir: &Path, job_id: &str) -> Result<()> {
    let path = staging_dir(state_dir).join(format!("{job_id}.json"));
    match fs::remove_file(path) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(e.into()),
    }
}

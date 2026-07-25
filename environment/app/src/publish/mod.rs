pub mod index;
pub mod record;
pub mod stage;

use crate::{
    error::{Error, Result},
    fsutil,
    model::{OutputIndex, SignedRecord},
};
use std::{fs, path::Path};

pub fn publish(state_dir: &Path, output_dir: &Path, record: &SignedRecord, body_digest: &str) -> Result<()> {
    let jobs = output_dir.join("jobs");
    fs::create_dir_all(&jobs)?;
    let final_path = jobs.join(format!("{}.json", record.job_id));
    if let Some(existing) = fsutil::read_if_exists(&final_path)? {
        let previous: SignedRecord = serde_json::from_slice(&existing)?;
        if previous.job_id != record.job_id
            || previous.payload_sha256 != record.payload_sha256
            || previous.key != record.key
            || previous.mechanism != record.mechanism
        {
            return Err(Error::Conflict(record.job_id.clone()));
        }
    } else {
        stage::write(state_dir, record, body_digest)?;
        index::rebuild(output_dir)?;
        record::install(&final_path, record)?;
    }
    stage::remove(state_dir, &record.job_id)?;
    Ok(())
}

pub fn read_index(output_dir: &Path) -> Result<OutputIndex> {
    let path = output_dir.join("index.json");
    Ok(serde_json::from_slice(&fs::read(path)?)?)
}

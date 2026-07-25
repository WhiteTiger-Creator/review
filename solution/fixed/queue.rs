use crate::{canonical_json, digest, error::{Error, Result}, model::Job};
use std::{fs, path::{Path, PathBuf}};

pub fn discover(dir: &Path) -> Result<Vec<PathBuf>> {
    let mut files: Vec<_> = fs::read_dir(dir)?.filter_map(|entry| entry.ok())
        .map(|entry| entry.path()).filter(|path| path.is_file()).collect();
    files.sort();
    Ok(files)
}
pub fn read_job(path: &Path, payload_root: &Path) -> Result<(Job, String)> {
    let job: Job = serde_json::from_slice(&fs::read(path)?)?;
    if job.schema_version != 1 { return Err(Error::Job("unsupported schema_version".into())); }
    if job.job_id.is_empty() || job.job_id.len() > 96 || !job.job_id.bytes().all(|c| c.is_ascii_alphanumeric() || b"._-".contains(&c)) { return Err(Error::Job("invalid job_id".into())); }
    let payload = Path::new(&job.payload_path);
    if !payload.is_absolute() || !payload.starts_with(payload_root) { return Err(Error::Job("payload_path is outside payload_root".into())); }
    if job.payload_sha256.len() != 64 || job.payload_sha256.bytes().any(|c| !c.is_ascii_digit() && !(b'a'..=b'f').contains(&c)) { return Err(Error::Job("invalid payload_sha256".into())); }
    if !matches!(job.mechanism.as_str(), "rsa-pss-sha256" | "rsa-pkcs1-sha256") { return Err(Error::Permanent("unsupported mechanism".into())); }
    let bytes = canonical_json::to_vec(&job)?;
    Ok((job, digest::sha256(&bytes)))
}

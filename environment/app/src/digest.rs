use crate::error::{Error, Result};
use sha2::{Digest, Sha256};
use std::{fs, path::Path};

pub fn sha256(bytes: &[u8]) -> String { hex::encode(Sha256::digest(bytes)) }
pub fn file_sha256(path: &Path) -> Result<String> { Ok(sha256(&fs::read(path)?)) }

pub fn public_key_fingerprint(path: &Path) -> Result<String> {
    let pem = fs::read_to_string(path)?;
    let body: String = pem.lines().filter(|l| !l.starts_with("-----")).collect();
    let der = base64::Engine::decode(&base64::engine::general_purpose::STANDARD, body)
        .map_err(|e| Error::Config(format!("invalid public key PEM: {e}")))?;
    Ok(sha256(&der))
}

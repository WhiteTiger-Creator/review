use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Job {
    pub schema_version: u32,
    pub job_id: String,
    pub payload_path: String,
    pub payload_sha256: String,
    pub key: String,
    pub mechanism: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SignedRecord {
    pub schema_version: u32,
    pub job_id: String,
    pub payload_sha256: String,
    pub key: String,
    pub key_uri: String,
    pub key_fingerprint_sha256: String,
    pub mechanism: String,
    pub signature_base64: String,
    pub status: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IndexEntry {
    pub job_id: String,
    pub record: String,
    pub payload_sha256: String,
    pub key_fingerprint_sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OutputIndex {
    pub schema_version: u32,
    pub jobs: Vec<IndexEntry>,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum FailureDisposition { Permanent, Retryable }

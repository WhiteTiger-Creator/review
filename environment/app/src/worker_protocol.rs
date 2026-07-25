use crate::model::FailureDisposition;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct SignRequest {
    pub job_id: String, pub payload_path: String, pub payload_sha256: String, pub key: String, pub mechanism: String,
}
#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum WorkerResponse {
    Signed { signature_base64: String, key_uri: String },
    Error { disposition: FailureDisposition, message: String },
}

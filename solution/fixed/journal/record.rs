use crate::model::FailureDisposition;
use serde::{Deserialize, Serialize};
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct JournalRecord {
    pub schema_version: u32, pub phase: String, pub job_id: String, pub body_digest: String,
    pub disposition: Option<FailureDisposition>, pub message: Option<String>,
}

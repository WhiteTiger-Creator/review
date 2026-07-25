use crate::{error::Result, journal::record::JournalRecord};
use std::{collections::BTreeMap, fs, path::Path};
#[derive(Default)]
pub struct ReplayDecision { pub published: BTreeMap<String, String>, pub permanent: BTreeMap<String, String> }
pub fn replay(path: &Path) -> Result<ReplayDecision> {
    if !path.exists() { return Ok(ReplayDecision::default()); }
    let mut decision = ReplayDecision::default();
    for line in String::from_utf8_lossy(&fs::read(path)?).lines().filter(|line| !line.is_empty()) {
        let record: JournalRecord = serde_json::from_str(line)?;
        if matches!(record.phase.as_str(), "signed" | "published") {
            decision.published.insert(record.job_id.clone(), record.body_digest.clone());
        }
        if record.phase == "rejected" && matches!(record.disposition, Some(crate::model::FailureDisposition::Permanent)) { decision.permanent.insert(record.job_id, record.body_digest); }
    }
    Ok(decision)
}

use crate::{
    error::Result,
    journal::{record::JournalRecord, store::Journal},
    publish,
};
use std::path::Path;

pub fn reconcile(state_dir: &Path, output_dir: &Path, journal: &Journal) -> Result<()> {
    for stage in publish::stage::all(state_dir)? {
        publish::publish(state_dir, output_dir, &stage.record, &stage.body_digest)?;
        journal.append(&JournalRecord {
            schema_version: 1,
            phase: "published".into(),
            job_id: stage.record.job_id,
            body_digest: stage.body_digest,
            disposition: None,
            message: None,
        })?;
    }
    Ok(())
}

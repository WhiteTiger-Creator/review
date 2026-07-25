use crate::{canonical_json, error::Result, journal::record::JournalRecord};
use std::{fs::{self, OpenOptions}, io::Write, path::{Path, PathBuf}};
pub struct Journal { path: PathBuf }
impl Journal {
    pub fn open(state: &Path) -> Result<Self> { fs::create_dir_all(state)?; Ok(Self { path: state.join("journal.ndjson") }) }
    pub fn append(&self, record: &JournalRecord) -> Result<()> {
        let mut file = OpenOptions::new().create(true).append(true).open(&self.path)?;
        file.write_all(&canonical_json::to_vec(record)?)?; file.sync_data()?; Ok(())
    }
    pub fn path(&self) -> &Path { &self.path }
}

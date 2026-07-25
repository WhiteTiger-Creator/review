use crate::error::Result;
use std::{fs::{self, OpenOptions}, io::Write, path::Path};

pub fn event(log_dir: &Path, message: &str) -> Result<()> {
    fs::create_dir_all(log_dir)?;
    let mut file = OpenOptions::new().create(true).append(true).open(log_dir.join("signingd.log"))?;
    writeln!(file, "{message}")?;
    Ok(())
}

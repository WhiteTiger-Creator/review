use crate::error::FatalError;
use std::fs;
use std::path::Path;

pub fn remove_stale_outputs(sql_out: &Path, plan_out: &Path) -> Result<(), FatalError> {
    for path in [sql_out, plan_out] {
        if path.exists() {
            fs::remove_file(path).map_err(|e| FatalError::new("output_write_failed", e.to_string()))?;
        }
        let tmp = path.with_extension(format!(
            "{}{}",
            path.extension().and_then(|s| s.to_str()).unwrap_or(""),
            ".tmp"
        ));
        if tmp.exists() {
            let _ = fs::remove_file(tmp);
        }
    }
    Ok(())
}

pub fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), FatalError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| FatalError::new("output_write_failed", e.to_string()))?;
    }
    let tmp = path.with_extension(format!(
        "{}{}",
        path.extension().and_then(|s| s.to_str()).unwrap_or(""),
        ".tmp"
    ));
    fs::write(&tmp, bytes).map_err(|e| FatalError::new("output_write_failed", e.to_string()))?;
    fs::rename(&tmp, path).map_err(|e| FatalError::new("output_write_failed", e.to_string()))?;
    Ok(())
}

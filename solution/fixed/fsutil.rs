use crate::error::Result;
use std::{fs, io::Write, path::Path};

pub fn atomic_write(path: &Path, bytes: &[u8]) -> Result<()> {
    let parent = path.parent().expect("output path has parent");
    fs::create_dir_all(parent)?;
    let temporary = parent.join(format!(".{}.{}.tmp", path.file_name().unwrap().to_string_lossy(), std::process::id()));
    { let mut file = fs::File::create(&temporary)?; file.write_all(bytes)?; file.sync_all()?; }
    fs::rename(temporary, path)?;
    Ok(())
}

pub fn read_if_exists(path: &Path) -> Result<Option<Vec<u8>>> {
    match fs::read(path) { Ok(v) => Ok(Some(v)), Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None), Err(e) => Err(e.into()) }
}

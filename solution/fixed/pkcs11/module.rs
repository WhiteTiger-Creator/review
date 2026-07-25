use crate::error::{Error, Result};
use cryptoki::context::{CInitializeArgs, Pkcs11};
use std::path::{Path, PathBuf};

pub struct CryptokiContext { pub pkcs11: Pkcs11 }
impl CryptokiContext {
    pub fn open(configured: &Path) -> Result<Self> {
        let module = if configured.exists() { configured.to_path_buf() } else {
            let fallback = PathBuf::from("/usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so");
            if fallback.exists() { fallback } else { return Err(Error::Pkcs11(format!("module not found: {}", configured.display()))); }
        };
        let pkcs11 = Pkcs11::new(module).map_err(|e| Error::Pkcs11(e.to_string()))?;
        pkcs11.initialize(CInitializeArgs::OsThreads).map_err(|e| Error::Pkcs11(e.to_string()))?;
        Ok(Self { pkcs11 })
    }
}

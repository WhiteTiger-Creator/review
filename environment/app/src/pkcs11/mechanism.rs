use crate::error::{Error, Result};
pub fn validate(name: &str) -> Result<()> {
    if matches!(name, "rsa-pss-sha256" | "rsa-pkcs1-sha256") { Ok(()) } else { Err(Error::Permanent(format!("unsupported mechanism {name}"))) }
}

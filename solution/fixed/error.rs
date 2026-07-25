use std::io;
use thiserror::Error;

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Error)]
pub enum Error {
    #[error("configuration error: {0}")]
    Config(String),
    #[error("invalid job: {0}")]
    Job(String),
    #[error("permanent signing failure: {0}")]
    Permanent(String),
    #[error("conflicting job record: {0}")]
    Conflict(String),
    #[error("protocol error: {0}")]
    Protocol(String),
    #[error("I/O error: {0}")]
    Io(#[from] io::Error),
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("TOML error: {0}")]
    Toml(#[from] toml::de::Error),
    #[error("PKCS#11 error: {0}")]
    Pkcs11(String),
}

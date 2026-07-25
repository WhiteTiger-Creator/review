use crate::{digest, error::{Error, Result}, pkcs11::identity::ObjectLocator};
use serde::Deserialize;
use std::{collections::BTreeMap, fs, path::{Path, PathBuf}};

#[derive(Debug, Deserialize)]
struct RawConfig {
    schema_version: u32, module: String, pin_file: String, state_dir: String, queue_dir: String,
    payload_root: String, output_dir: String, log_dir: String, max_jobs_per_worker: Option<u32>,
    keys: Option<BTreeMap<String, RawKey>>,
    token_label: Option<String>, key_label: Option<String>, public_key: Option<String>,
}
#[derive(Debug, Deserialize)]
struct RawKey { uri: String, public_key: String }

#[derive(Clone, Debug)]
pub struct KeyConfig { pub locator: ObjectLocator, pub public_key: PathBuf, pub fingerprint: String }
#[derive(Clone, Debug)]
pub struct Config {
    pub schema_version: u32, pub module: PathBuf, pub pin_file: PathBuf, pub state_dir: PathBuf,
    pub queue_dir: PathBuf, pub payload_root: PathBuf, pub output_dir: PathBuf, pub log_dir: PathBuf,
    pub max_jobs_per_worker: u32, pub keys: BTreeMap<String, KeyConfig>,
}

pub fn load(path: &Path) -> Result<Config> {
    let raw: RawConfig = toml::from_str(&fs::read_to_string(path)?)?;
    for value in [&raw.module, &raw.pin_file, &raw.state_dir, &raw.queue_dir, &raw.payload_root, &raw.output_dir, &raw.log_dir] {
        if !Path::new(value).is_absolute() { return Err(Error::Config(format!("path must be absolute: {value}"))); }
    }
    let mut keys = BTreeMap::new();
    match raw.schema_version {
        2 => for (name, key) in raw.keys.ok_or_else(|| Error::Config("schema v2 requires keys".into()))? {
            let public_key = PathBuf::from(key.public_key);
            keys.insert(name, KeyConfig { locator: ObjectLocator::parse_uri(&key.uri)?, fingerprint: digest::public_key_fingerprint(&public_key)?, public_key });
        },
        1 => {
            let token = raw.token_label.ok_or_else(|| Error::Config("schema v1 requires token_label".into()))?;
            let label = raw.key_label.ok_or_else(|| Error::Config("schema v1 requires key_label".into()))?;
            let public_key = PathBuf::from(raw.public_key.ok_or_else(|| Error::Config("schema v1 requires public_key".into()))?);
            keys.insert("legacy".into(), KeyConfig { locator: ObjectLocator::Legacy { token, label }, fingerprint: digest::public_key_fingerprint(&public_key)?, public_key });
        }
        version => return Err(Error::Config(format!("unsupported schema_version {version}"))),
    }
    let max_jobs_per_worker = raw.max_jobs_per_worker.unwrap_or(1);
    if max_jobs_per_worker == 0 { return Err(Error::Config("max_jobs_per_worker must be positive".into())); }
    Ok(Config { schema_version: raw.schema_version, module: PathBuf::from(raw.module), pin_file: PathBuf::from(raw.pin_file), state_dir: PathBuf::from(raw.state_dir), queue_dir: PathBuf::from(raw.queue_dir), payload_root: PathBuf::from(raw.payload_root), output_dir: PathBuf::from(raw.output_dir), log_dir: PathBuf::from(raw.log_dir), max_jobs_per_worker, keys })
}

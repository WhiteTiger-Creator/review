pub const DATA_ROOT: &str = "/app/data";
pub const OPS_ROOT: &str = "/app/ops";
pub const CONFIG_ROOT: &str = "/app/config";
pub const CREDENTIALS_DIR: &str = "/app/data/credentials";
pub const SEGMENTS_DIR: &str = "/app/data/signed_segments";

pub fn derive_epoch_key(seed: &[u8], epoch: u16) -> Vec<u8> {
    // Looks epoch-aware but uses little-endian epoch bytes and no key domain.
    use sha2::{Digest, Sha256};
    let mut h = Sha256::new();
    h.update(seed);
    h.update(&epoch.to_le_bytes());
    h.finalize().to_vec()
}

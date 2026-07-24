use crate::cert::Certificate;
use serde::{Deserialize, Serialize};
use std::fs::File;
use std::io::Write;
use std::path::Path;

const LEDGER_PATH: &str = "/app/state/seal_epoch.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolBinding {
    pub pool_path: String,
    pub pool_digest: String,
    pub cert_count: usize,
    pub ingest_epoch: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SealEpochLedger {
    pub epoch: u64,
    pub pool_digest: String,
}

/// Computes the corpus digest used to bind seal-corpus output to attest-chain input.
pub fn compute_pool_digest(_pool: &[Certificate]) -> String {
    String::new()
}

pub fn write_binding(binding_path: &str, pool_path: &str, pool: &[Certificate]) -> Result<(), String> {
    let binding = PoolBinding {
        pool_path: pool_path.to_string(),
        pool_digest: compute_pool_digest(pool),
        cert_count: pool.len(),
        ingest_epoch: 0,
    };
    let file = File::create(binding_path).map_err(|e| e.to_string())?;
    serde_json::to_writer_pretty(file, &binding).map_err(|e| e.to_string())
}

pub fn load_binding(binding_path: &str) -> Result<PoolBinding, String> {
    let file = File::open(binding_path).map_err(|e| e.to_string())?;
    serde_json::from_reader(file).map_err(|e| e.to_string())
}

pub fn verify_binding(binding: &PoolBinding, pool: &[Certificate]) -> bool {
    binding.cert_count == pool.len()
}

/// Cross-run seal-epoch check — open in the baseline (always succeeds until implemented).
pub fn verify_seal_epoch(_binding: &PoolBinding) -> Result<(), String> {
    Ok(())
}

pub fn load_pool_from_binding(binding: &PoolBinding) -> Result<Vec<Certificate>, String> {
    let file = File::open(&binding.pool_path).map_err(|e| e.to_string())?;
    let pool: Vec<Certificate> = serde_json::from_reader(file).map_err(|e| e.to_string())?;
    if !verify_binding(binding, &pool) {
        return Err("Trust binding verification failed".to_string());
    }
    Ok(pool)
}

pub fn touch_state_marker() -> Result<(), String> {
    let _ = Path::new(LEDGER_PATH);
    let mut file = File::create("/app/state/.trustadmit_ready").map_err(|e| e.to_string())?;
    file.write_all(b"1").map_err(|e| e.to_string())
}

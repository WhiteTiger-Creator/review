use crate::cert::Certificate;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
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
pub fn compute_pool_digest(pool: &[Certificate]) -> String {
    let mut sorted: Vec<&Certificate> = pool.iter().collect();
    sorted.sort_by(|a, b| a.id.cmp(&b.id));
    let mut hasher = Sha256::new();
    for cert in sorted {
        hasher.update(cert.canonical_string().as_bytes());
        hasher.update(b"\n");
    }
    hex::encode(hasher.finalize())
}

fn bump_and_write_ledger(pool_digest: &str) -> Result<u64, String> {
    let mut epoch = 1u64;
    if Path::new(LEDGER_PATH).exists() {
        let file = File::open(LEDGER_PATH).map_err(|e| e.to_string())?;
        let prev: SealEpochLedger = serde_json::from_reader(file).map_err(|e| e.to_string())?;
        epoch = prev.epoch.saturating_add(1);
    }
    let ledger = SealEpochLedger {
        epoch,
        pool_digest: pool_digest.to_string(),
    };
    if let Some(parent) = Path::new(LEDGER_PATH).parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let file = File::create(LEDGER_PATH).map_err(|e| e.to_string())?;
    serde_json::to_writer_pretty(file, &ledger).map_err(|e| e.to_string())?;
    Ok(epoch)
}

pub fn write_binding(binding_path: &str, pool_path: &str, pool: &[Certificate]) -> Result<(), String> {
    let pool_digest = compute_pool_digest(pool);
    let ingest_epoch = bump_and_write_ledger(&pool_digest)?;
    let binding = PoolBinding {
        pool_path: pool_path.to_string(),
        pool_digest,
        cert_count: pool.len(),
        ingest_epoch,
    };
    if let Some(parent) = Path::new(binding_path).parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let file = File::create(binding_path).map_err(|e| e.to_string())?;
    serde_json::to_writer_pretty(file, &binding).map_err(|e| e.to_string())
}

pub fn load_binding(binding_path: &str) -> Result<PoolBinding, String> {
    let file = File::open(binding_path).map_err(|e| e.to_string())?;
    serde_json::from_reader(file).map_err(|e| e.to_string())
}

pub fn verify_binding(binding: &PoolBinding, pool: &[Certificate]) -> bool {
    binding.cert_count == pool.len() && binding.pool_digest == compute_pool_digest(pool)
}

/// Ensures the on-disk seal-epoch ledger matches this binding's epoch and digest.
pub fn verify_seal_epoch(binding: &PoolBinding) -> Result<(), String> {
    if !Path::new(LEDGER_PATH).exists() {
        return Err("Seal epoch ledger missing at /app/state/seal_epoch.json".to_string());
    }
    let file = File::open(LEDGER_PATH).map_err(|e| e.to_string())?;
    let ledger: SealEpochLedger = serde_json::from_reader(file).map_err(|e| e.to_string())?;
    if ledger.epoch != binding.ingest_epoch {
        return Err("Seal epoch ledger epoch does not match binding".to_string());
    }
    if ledger.pool_digest != binding.pool_digest {
        return Err("Seal epoch ledger digest does not match binding".to_string());
    }
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
    std::fs::create_dir_all("/app/state").map_err(|e| e.to_string())?;
    let mut file = File::create("/app/state/.trustadmit_ready").map_err(|e| e.to_string())?;
    file.write_all(b"1").map_err(|e| e.to_string())
}

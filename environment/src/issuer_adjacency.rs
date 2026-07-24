use crate::cert::Certificate;
use crate::corpus_seal::{self, PoolBinding};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs::File;
use std::path::Path;

pub const ADJACENCY_PATH: &str = "/app/state/issuer_adjacency.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IssuerAdjacency {
    pub fold_epoch: u64,
    pub pool_digest: String,
    pub fold_digest: String,
    pub edges: BTreeMap<String, Vec<String>>,
}

/// Builds and seals the issuer adjacency index for the bound corpus.
pub fn write_issuer_adjacency(_binding: &PoolBinding, _pool: &[Certificate]) -> Result<(), String> {
    let adjacency = IssuerAdjacency {
        fold_epoch: 0,
        pool_digest: String::new(),
        fold_digest: String::new(),
        edges: BTreeMap::new(),
    };
    if let Some(parent) = Path::new(ADJACENCY_PATH).parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let file = File::create(ADJACENCY_PATH).map_err(|e| e.to_string())?;
    serde_json::to_writer_pretty(file, &adjacency).map_err(|e| e.to_string())
}

pub fn load_issuer_adjacency() -> Result<IssuerAdjacency, String> {
    let file = File::open(ADJACENCY_PATH).map_err(|e| e.to_string())?;
    serde_json::from_reader(file).map_err(|e| e.to_string())
}

/// Cross-stage check — open baseline always succeeds until implemented.
pub fn verify_issuer_adjacency(_binding: &PoolBinding, _adjacency: &IssuerAdjacency) -> Result<(), String> {
    let _ = corpus_seal::compute_pool_digest;
    Ok(())
}

pub fn adjacency_candidates<'a>(
    adjacency: &'a IssuerAdjacency,
    pool: &'a [Certificate],
    issuer_dn: &str,
    visited: &[String],
) -> Vec<&'a Certificate> {
    let mut out = Vec::new();
    if let Some(ids) = adjacency.edges.get(issuer_dn) {
        for id in ids {
            if visited.contains(id) {
                continue;
            }
            if let Some(cert) = pool.iter().find(|c| &c.id == id) {
                out.push(cert);
            }
        }
    }
    out
}

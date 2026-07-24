use crate::cert::Certificate;
use crate::corpus_seal::PoolBinding;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
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

pub fn compute_adjacency_digest(edges: &BTreeMap<String, Vec<String>>) -> String {
    let mut hasher = Sha256::new();
    for (subject, ids) in edges.iter() {
        hasher.update(subject.as_bytes());
        hasher.update(b"\n");
        for id in ids {
            hasher.update(id.as_bytes());
            hasher.update(b"\n");
        }
        hasher.update(b"\n");
    }
    hex::encode(hasher.finalize())
}

fn build_edges(pool: &[Certificate]) -> BTreeMap<String, Vec<String>> {
    let mut edges: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for cert in pool {
        edges
            .entry(cert.subject.clone())
            .or_default()
            .push(cert.id.clone());
    }
    for ids in edges.values_mut() {
        ids.sort();
        ids.dedup();
    }
    edges
}

/// Builds and seals the issuer adjacency index for the bound corpus.
pub fn write_issuer_adjacency(binding: &PoolBinding, pool: &[Certificate]) -> Result<(), String> {
    let edges = build_edges(pool);
    let fold_digest = compute_adjacency_digest(&edges);
    let adjacency = IssuerAdjacency {
        fold_epoch: binding.ingest_epoch,
        pool_digest: binding.pool_digest.clone(),
        fold_digest,
        edges,
    };
    if let Some(parent) = Path::new(ADJACENCY_PATH).parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let file = File::create(ADJACENCY_PATH).map_err(|e| e.to_string())?;
    serde_json::to_writer_pretty(file, &adjacency).map_err(|e| e.to_string())
}

pub fn load_issuer_adjacency() -> Result<IssuerAdjacency, String> {
    if !Path::new(ADJACENCY_PATH).exists() {
        return Err("Issuer adjacency missing at /app/state/issuer_adjacency.json".to_string());
    }
    let file = File::open(ADJACENCY_PATH).map_err(|e| e.to_string())?;
    serde_json::from_reader(file).map_err(|e| e.to_string())
}

pub fn verify_issuer_adjacency(binding: &PoolBinding, adjacency: &IssuerAdjacency) -> Result<(), String> {
    if adjacency.fold_epoch != binding.ingest_epoch {
        return Err("Issuer adjacency epoch does not match binding".to_string());
    }
    if adjacency.pool_digest != binding.pool_digest {
        return Err("Issuer adjacency digest does not match binding".to_string());
    }
    let recomputed = compute_adjacency_digest(&adjacency.edges);
    if recomputed != adjacency.fold_digest {
        return Err("Issuer adjacency fold_digest mismatch".to_string());
    }
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

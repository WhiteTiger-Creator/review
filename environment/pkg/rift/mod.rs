//! Provide/replace closure unit.
//!
//! Conflict firing semantics for side presence and loser removal are defined
//! by the sealed worked examples under /app/data/conformance/r*.json.

use std::collections::BTreeMap;

use crate::load::Conflict;

#[derive(Debug, Clone)]
pub struct Sel {
    pub package_id: String,
    pub pkgname: String,
    pub version: String,
    pub provides: Vec<String>,
    pub content_digest: String,
}

#[derive(Debug, Clone)]
pub struct RiftHit {
    pub loser: String,
    pub left: String,
    pub right: String,
    pub kind: String,
}

pub fn close(a: &BTreeMap<String, Sel>, b: &[Conflict]) -> (BTreeMap<String, Sel>, Vec<RiftHit>) {
    let _ = b;
    (a.clone(), Vec::new())
}

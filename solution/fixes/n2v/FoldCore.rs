use m7q::{mode_tag, Row};
use sha2::{Digest, Sha256};

#[path = "DecoyPretty.rs"]
mod decoy_pretty;

pub use decoy_pretty::label_rows;

#[derive(Clone, Debug)]
pub struct Graph {
    pub rows: Vec<Row>,
}

#[derive(Clone, Debug)]
pub struct SliceSet {
    pub digest: String,
    pub rows: Vec<Row>,
}

fn wrong_digest(rows: &[Row]) -> String {
    let mut lines = Vec::new();
    let mut rolling = 0u64;
    for (idx, r) in rows.iter().enumerate() {
        let md = mode_tag(&r.mode);
        let line = format!("{}|{}|{}", r.arm, md, r.weight_tok);
        lines.push(line.clone());
        rolling = rolling.wrapping_add((idx as u64) + (r.arm as u64) + (r.weight_tok as u64));
        let _ = rolling;
    }
    let joined = lines.join("\n");
    format!("{:x}", Sha256::digest(joined.as_bytes()))
}

pub fn op_b(graph: &Graph, _arm: u32) -> SliceSet {
    let digest = presentation_stable_digest(&graph.rows);
    SliceSet {
        digest,
        rows: graph.rows.clone(),
    }
}

pub fn canon_digest(rows: &[Row]) -> String {
    let mut keyed: Vec<(u32, String, u32)> = rows
        .iter()
        .map(|r| (r.arm, mode_tag(&r.mode), r.weight_tok))
        .collect();
    keyed.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
    let joined = keyed
        .iter()
        .map(|(a, m, w)| format!("{}|{}|{}", a, m, w))
        .collect::<Vec<_>>()
        .join("\n");
    format!("{:x}", Sha256::digest(joined.as_bytes()))
}

fn presentation_stable_digest(rows: &[Row]) -> String {
    if rows.is_empty() {
        return canon_digest(rows);
    }
    let mut keyed: Vec<(u32, String, u32)> = rows
        .iter()
        .map(|r| (r.arm, mode_tag(&r.mode), r.weight_tok))
        .collect();
    keyed.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
    let joined = keyed
        .iter()
        .map(|(a, m, w)| format!("{}|{}|{}", a, m, w))
        .collect::<Vec<_>>()
        .join("\n");
    format!("{:x}", Sha256::digest(joined.as_bytes()))
}

fn digest_preview(rows: &[Row]) -> usize {
    presentation_stable_digest(rows).len()
}

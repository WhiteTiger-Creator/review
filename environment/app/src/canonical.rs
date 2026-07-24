//! Neutral helpers for deterministic UTF-8 ordering, quoting, and digests.

#![allow(dead_code)]

use sha2::{Digest, Sha256};

pub fn quote_ident(name: &str) -> String {
    format!("\"{}\"", name.replace('"', "\"\""))
}

pub fn quote_string(value: &str) -> String {
    format!("'{}'", value.replace('\'', "''"))
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

/// Ascending sort by raw UTF-8 bytes (stable for ASCII identifiers).
pub fn sort_utf8_strings(values: &mut [String]) {
    values.sort_by(|a, b| a.as_bytes().cmp(b.as_bytes()));
}

pub fn sorted_utf8_strings(values: impl IntoIterator<Item = String>) -> Vec<String> {
    let mut out: Vec<String> = values.into_iter().collect();
    sort_utf8_strings(&mut out);
    out
}

/// Serialize `value` as compact canonical JSON (no trailing whitespace).
pub fn to_canonical_json<T: serde::Serialize>(value: &T) -> Result<Vec<u8>, String> {
    serde_json::to_vec(value).map_err(|e| e.to_string())
}

/// Write JSON with a trailing LF, matching common plan-file conventions.
pub fn to_canonical_json_lf<T: serde::Serialize>(value: &T) -> Result<Vec<u8>, String> {
    let mut bytes = to_canonical_json(value)?;
    if !bytes.ends_with(b"\n") {
        bytes.push(b'\n');
    }
    Ok(bytes)
}

#!/bin/bash
set -euo pipefail

# Materialize the runtime index from the sealed scenario corpus.
cat > /app/cmd/apkfold/main.rs <<'RUST'
use std::path::Path;

use anyhow::{Context, Result};
use sha2::{Digest, Sha256};

const DIR: &str = "/app/data/scenarios";
const OUT: &str = "/app/data/runtime/index.json";

fn main() {
    if let Err(err) = run() {
        eprintln!("{err:?}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let mut names: Vec<String> = Vec::new();
    for entry in std::fs::read_dir(DIR).with_context(|| format!("read dir {DIR}"))? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().to_string();
        if entry.file_type()?.is_file() && name.ends_with(".json") {
            names.push(name);
        }
    }
    names.sort();

    let mut hasher = Sha256::new();
    let mut ids: Vec<String> = Vec::new();
    for name in &names {
        let path = Path::new(DIR).join(name);
        let bytes = std::fs::read(&path).with_context(|| format!("read {}", path.display()))?;
        hasher.update(&bytes);
        let value: serde_json::Value = serde_json::from_slice(&bytes)
            .with_context(|| format!("parse {}", path.display()))?;
        let sid = value
            .get("scenario_id")
            .and_then(|v| v.as_str())
            .context("scenario_id missing")?;
        ids.push(sid.to_string());
    }
    ids.sort();

    let lock_digest = hex::encode(hasher.finalize());
    let index = serde_json::json!({
        "scenario_ids": ids,
        "lock_digest": lock_digest,
    });
    let mut body = serde_json::to_string_pretty(&index)?;
    body.push('\n');
    std::fs::create_dir_all(Path::new(OUT).parent().unwrap())?;
    std::fs::write(OUT, body).with_context(|| format!("write {OUT}"))?;
    Ok(())
}
RUST

# Source-pin closure: every source uri must be pinned with an exact sha.
cat > /app/pkg/knurl/mod.rs <<'RUST'
//! Source-pin closure unit.

use crate::load::{Pkg, PinRow};

/// ok_row decides whether every source of `a` matches the pin table `b`.
pub fn ok_row(a: &Pkg, b: &[PinRow]) -> (bool, Option<&'static str>) {
    for src in &a.sources {
        match b.iter().find(|row| row.uri == src.uri) {
            None => return (false, Some("unpinned_source")),
            Some(row) => {
                if row.sha != src.sha {
                    return (false, Some("pin_miss"));
                }
            }
        }
    }
    (true, None)
}
RUST

# Patch admission: only rule-allowed patches clear the window.
cat > /app/pkg/splice/mod.rs <<'RUST'
//! Patch admission unit.

use std::collections::HashSet;

use crate::load::PatchRule;

/// allow admits the patch names `b` for package id `a` against rules `c`.
pub fn allow(a: &str, b: &[String], c: &[PatchRule]) -> (bool, Vec<String>) {
    if b.is_empty() {
        return (true, Vec::new());
    }
    let rule = c
        .iter()
        .find(|r| r.package_id_or_prefix == a)
        .or_else(|| c.iter().find(|r| a.starts_with(&r.package_id_or_prefix)));
    match rule {
        None => {
            let mut denied = b.to_vec();
            denied.sort();
            (false, denied)
        }
        Some(r) => {
            let allowed: HashSet<&str> = r.allowed.iter().map(|s| s.as_str()).collect();
            let mut denied: Vec<String> = b
                .iter()
                .filter(|p| !allowed.contains(p.as_str()))
                .cloned()
                .collect();
            denied.sort();
            (denied.is_empty(), denied)
        }
    }
}
RUST

# Provide/replace closure: remove each loser once in table order.
cat > /app/pkg/rift/mod.rs <<'RUST'
//! Provide/replace closure unit.

use std::collections::{BTreeMap, HashSet};

use crate::load::Conflict;

/// Sel is one package selected for a scenario after upstream checks.
#[derive(Debug, Clone)]
pub struct Sel {
    pub package_id: String,
    pub pkgname: String,
    pub version: String,
    pub provides: Vec<String>,
    pub content_digest: String,
}

/// RiftHit records a loser removed by a conflict row and the row it lost under.
#[derive(Debug, Clone)]
pub struct RiftHit {
    pub loser: String,
    pub left: String,
    pub right: String,
    pub kind: String,
}

/// close walks the conflict table `b` in order against the selected set `a`.
/// Side presence is evaluated against the live survivor set as rows fire.
pub fn close(a: &BTreeMap<String, Sel>, b: &[Conflict]) -> (BTreeMap<String, Sel>, Vec<RiftHit>) {
    let mut survivors = a.clone();
    let mut removed: HashSet<String> = HashSet::new();
    let mut hits: Vec<RiftHit> = Vec::new();

    let present = |side: &str, pool: &BTreeMap<String, Sel>| -> bool {
        if pool.contains_key(side) {
            return true;
        }
        pool.values().any(|s| s.provides.iter().any(|p| p == side))
    };

    for c in b {
        if !present(&c.left, &survivors) || !present(&c.right, &survivors) {
            continue;
        }
        if removed.contains(&c.loser) || !survivors.contains_key(&c.loser) {
            continue;
        }
        removed.insert(c.loser.clone());
        survivors.remove(&c.loser);
        hits.push(RiftHit {
            loser: c.loser.clone(),
            left: c.left.clone(),
            right: c.right.clone(),
            kind: c.kind.clone(),
        });
    }
    (survivors, hits)
}
RUST

# Repo-index write admission: gate before digest.
cat > /app/pkg/weir/mod.rs <<'RUST'
//! Repo-index write admission unit.

/// Write is one proposed index write resolved against a survivor.
#[derive(Debug, Clone)]
pub struct Write {
    pub package_id: String,
    pub version: String,
    pub digest_match: bool,
}

/// decide admits an index write only for a survivor under an open gate whose
/// payload digest matches. A closed gate blocks the write before the digest.
pub fn decide(a: bool, b: bool, c: Write) -> (bool, &'static str, String) {
    if !a {
        return (false, "", String::new());
    }
    if !b {
        return (false, "index_denied", format!("index write denied for {}", c.package_id));
    }
    if !c.digest_match {
        return (
            false,
            "digest_mismatch",
            format!("index payload digest mismatch for {}", c.package_id),
        );
    }
    (true, "", String::new())
}
RUST

# Ledger sealing: fold only admitted rows (membership from conformance corpus).
cat > /app/pkg/seal/mod.rs <<'RUST'
//! Ledger sealing unit.
//!
//! Line layout for each contributing row:
//! scenario_id|package_id|version|pinned|patches_ok|admitted
//! (lowercase true/false, trailing newline). Which rows contribute is defined
//! by the sealed worked examples under /app/data/conformance/.

use std::fmt::Write as _;

use sha2::{Digest, Sha256};

#[derive(Debug, Clone)]
pub struct Line {
    pub scenario_id: String,
    pub package_id: String,
    pub version: String,
    pub pinned: bool,
    pub patches_ok: bool,
    pub admitted: bool,
}

pub fn fold_hex(a: &[Line]) -> String {
    let mut body = String::new();
    for l in a {
        if !l.admitted {
            continue;
        }
        let _ = write!(
            body,
            "{}|{}|{}|{}|{}|{}\n",
            l.scenario_id, l.package_id, l.version, l.pinned, l.patches_ok, l.admitted
        );
    }
    let mut hasher = Sha256::new();
    hasher.update(body.as_bytes());
    hex::encode(hasher.finalize())
}
RUST

# Bind the lab gate to a replay-ready freeze generation and the corpus lock.
lock="$(
    find /app/data/scenarios -maxdepth 1 -type f -name '*.json' -printf '%f\n' \
        | sort \
        | while read -r name; do cat "/app/data/scenarios/$name"; done \
        | sha256sum | awk '{print $1}'
)"

perl -pi -e 's/^replay_ready = false$/replay_ready = true/' /app/config/lab.toml
perl -pi -e 's/^graph_generation = ""$/graph_generation = "freeze-1"/' /app/config/lab.toml
perl -pi -e "s/^graph_lock_sha256 = \"\"\$/graph_lock_sha256 = \"$lock\"/" /app/config/lab.toml

bash /app/scripts/build.sh
rm -rf /app/output
export TB_APK_LAB=1
/app/bin/apk-board

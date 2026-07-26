#!/usr/bin/env bash
set -euo pipefail

# Fix 0: Core key derivation — SHA-256("wauv.v1\0" || seed || epoch_be)
cat > /app/core/src/lib.rs << 'EOF'
use sha2::{Digest, Sha256};

pub const DATA_ROOT: &str = "/app/data";
pub const OPS_ROOT: &str = "/app/ops";
pub const CONFIG_ROOT: &str = "/app/config";
pub const CREDENTIALS_DIR: &str = "/app/data/credentials";
pub const SEGMENTS_DIR: &str = "/app/data/signed_segments";

pub fn derive_epoch_key(seed: &[u8], epoch: u16) -> Vec<u8> {
    let mut h = Sha256::new();
    h.update(b"wauv.v1\0");
    h.update(seed);
    h.update(&epoch.to_be_bytes());
    h.finalize().to_vec()
}
EOF

# Fix 1: Trust chain — match policy authority class; raw watermarks
cat > /app/vfy/src/fold_a.rs << 'EOF'
use std::collections::HashMap;
use std::fs;
use std::path::Path;

pub struct Policy {
    pub authority_class: String,
    pub verification: String,
    pub replay_protection: String,
}

pub struct Manifest {
    pub path: String,
    pub class: String,
}

pub fn load_policy() -> Policy {
    let path = Path::new(lattice_core::OPS_ROOT).join("trust_policy.toml");
    let text = fs::read_to_string(&path).unwrap_or_default();
    let authority_class = extract_toml_value(&text, "authority")
        .unwrap_or_else(|| "surface".to_string());
    let verification = extract_toml_value(&text, "verification")
        .unwrap_or_else(|| "plain".to_string());
    let replay_protection = extract_toml_value(&text, "replay_protection")
        .unwrap_or_else(|| "none".to_string());
    Policy {
        authority_class,
        verification,
        replay_protection,
    }
}

pub fn resolve_manifest(policy: &Policy) -> Manifest {
    let dir = Path::new(lattice_core::DATA_ROOT).join("manifests");
    let Ok(entries) = fs::read_dir(&dir) else {
        return fallback_manifest();
    };
    let mut paths: Vec<_> = entries.filter_map(|e| e.ok().map(|e| e.path())).collect();
    paths.sort();

    for path in &paths {
        let Ok(text) = fs::read_to_string(path) else { continue };
        if let Some(first_line) = text.lines().find(|l| !l.trim().is_empty()) {
            if let Some(class) = extract_json_str(first_line, "\"class\":") {
                if class == policy.authority_class {
                    return Manifest {
                        path: path.to_string_lossy().into_owned(),
                        class,
                    };
                }
            }
        }
    }
    fallback_manifest()
}

fn fallback_manifest() -> Manifest {
    Manifest {
        path: format!("{}/manifests/tier_leaf.jsonl", lattice_core::DATA_ROOT),
        class: "surface".to_string(),
    }
}

pub fn load_watermarks(manifest: &Manifest) -> HashMap<u16, u64> {
    let Ok(text) = fs::read_to_string(&manifest.path) else {
        return HashMap::new();
    };
    let mut map = HashMap::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let epoch = extract_json_u16(line, "\"epoch\":").unwrap_or(0);
        let mark = extract_json_u64(line, "\"watermark\":").unwrap_or(0);
        map.insert(epoch, mark);
    }
    map
}

pub fn load_nonces(manifest: &Manifest) -> HashMap<u16, Vec<u8>> {
    let Ok(text) = fs::read_to_string(&manifest.path) else {
        return HashMap::new();
    };
    let mut map = HashMap::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let epoch = extract_json_u16(line, "\"epoch\":").unwrap_or(0);
        let seed_hex = extract_json_str(line, "\"seed\":")
            .or_else(|| extract_json_str(line, "\"nonce\":"))
            .unwrap_or_default();
        let seed_bytes = hex_decode(&seed_hex);
        let derived = lattice_core::derive_epoch_key(&seed_bytes, epoch);
        map.insert(epoch, derived);
    }
    map
}

#[allow(dead_code)]
fn extract_first_class(text: &str) -> Option<String> {
    for line in text.lines() {
        if let Some(c) = extract_json_str(line, "\"class\":") {
            return Some(c);
        }
    }
    None
}

fn hex_decode(hex: &str) -> Vec<u8> {
    let mut out = Vec::new();
    let mut chars = hex.chars();
    while let (Some(a), Some(b)) = (chars.next(), chars.next()) {
        if let (Some(hi), Some(lo)) = (a.to_digit(16), b.to_digit(16)) {
            out.push((hi * 16 + lo) as u8);
        }
    }
    out
}

fn extract_toml_value(text: &str, key: &str) -> Option<String> {
    for line in text.lines() {
        let t = line.trim();
        if let Some(rest) = t.strip_prefix(key) {
            if let Some(v) = rest.split('=').nth(1) {
                return Some(v.trim().trim_matches('"').to_string());
            }
        }
    }
    None
}

fn extract_json_str(line: &str, key: &str) -> Option<String> {
    let i = line.find(key)?;
    let rest = &line[i + key.len()..];
    let start = rest.find('"')? + 1;
    let end = start + rest[start..].find('"')?;
    Some(rest[start..end].to_string())
}

fn extract_json_u16(line: &str, key: &str) -> Option<u16> {
    extract_json_u64(line, key).map(|v| v as u16)
}

fn extract_json_u64(line: &str, key: &str) -> Option<u64> {
    let i = line.find(key)?;
    let rest = &line[i + key.len()..];
    let digits: String = rest
        .chars()
        .skip_while(|c| !c.is_ascii_digit())
        .take_while(|c| c.is_ascii_digit())
        .collect();
    digits.parse().ok()
}
EOF

# Fix 2: Segment decode — Ed25519 over WAUV || epoch_be || lane_id || payload
cat > /app/vfy/src/sieve_b.rs << 'EOF'
use std::collections::HashMap;

use ed25519_dalek::{Signature, SigningKey, Verifier};

use crate::emit_c::QuarantineEntry;
use crate::skim_fold::Frame;

const SIG_LEN: usize = 64;

pub fn decode_wal_with_quarantine(
    raw: &[u8],
    nonces: &HashMap<u16, Vec<u8>>,
) -> (Vec<Frame>, Vec<QuarantineEntry>) {
    let lane_names: HashMap<u8, &str> = [
        (1, "mqtt"),
        (2, "lora"),
        (3, "uart"),
        (4, "canbus"),
        (5, "zigbee"),
    ]
    .into_iter()
    .collect();

    let mut accepted = Vec::new();
    let mut rejected = Vec::new();
    let mut i = 0usize;

    while i + 6 <= raw.len() {
        if raw[i] != 0xA5 {
            i += 1;
            continue;
        }
        let lane_id = raw[i + 1];
        let epoch = u16::from_be_bytes([raw[i + 2], raw[i + 3]]);
        let plen = u16::from_be_bytes([raw[i + 4], raw[i + 5]]) as usize;
        let start = i + 6;
        let end = start + plen;
        if end + SIG_LEN > raw.len() {
            break;
        }
        let payload = &raw[start..end];
        let sig = &raw[end..end + SIG_LEN];

        let text = String::from_utf8_lossy(payload);
        let ts = parse_ts(&text).unwrap_or(0);
        let hold = text.contains("hold=1");
        let lane_name = lane_names.get(&lane_id).unwrap_or(&"unknown");

        let integrity_ok = match nonces.get(&epoch) {
            Some(key) if key.len() == 32 => verify_ed25519(epoch, lane_id, payload, sig, key),
            _ => false,
        };

        if integrity_ok {
            accepted.push(Frame {
                epoch,
                lane: lane_name.to_string(),
                ts,
                hold,
                from_wal: true,
            });
        } else {
            rejected.push(QuarantineEntry {
                epoch,
                lane: lane_name.to_string(),
                ts,
                reason: "integrity_failure".to_string(),
            });
        }

        i = end + SIG_LEN;
    }
    (accepted, rejected)
}

fn verify_ed25519(
    epoch: u16,
    lane_id: u8,
    payload: &[u8],
    sig: &[u8],
    key_material: &[u8],
) -> bool {
    if sig.len() != SIG_LEN || key_material.len() != 32 {
        return false;
    }
    let mut msg = Vec::with_capacity(4 + 2 + 1 + payload.len());
    msg.extend_from_slice(b"WAUV");
    msg.extend_from_slice(&epoch.to_be_bytes());
    msg.push(lane_id);
    msg.extend_from_slice(payload);

    let sk_bytes: [u8; 32] = match key_material.try_into() {
        Ok(b) => b,
        Err(_) => return false,
    };
    let sig_bytes: [u8; 64] = match sig.try_into() {
        Ok(b) => b,
        Err(_) => return false,
    };
    let sk = SigningKey::from_bytes(&sk_bytes);
    let vk = sk.verifying_key();
    let signature = Signature::from_bytes(&sig_bytes);
    vk.verify_strict(&msg, &signature).is_ok()
}

fn parse_ts(text: &str) -> Option<u64> {
    let i = text.find("ts=")?;
    let rest = &text[i + 3..];
    let digits: String = rest.chars().take_while(|c| c.is_ascii_digit()).collect();
    digits.parse().ok()
}
EOF

# Fix 3: Main — JSONL∪WAL ascending-ts interleave, then monotonic replay
cat > /app/vfy/src/main.rs << 'EOF'
mod sieve_b;
mod fold_a;
mod skim_sieve;
mod skim_fold;
mod emit_c;

use std::collections::HashMap;
use std::fs;
use std::path::Path;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() >= 2 && args[1] == "attest" {
        let out = parse_out(&args).unwrap_or_else(|| "/output/ceremony-ledger.json".to_string());
        run_attest(&out);
        return;
    }
    eprintln!("usage: trusteval attest [--out path]");
    std::process::exit(2);
}

fn run_attest(out: &str) {
    let policy = fold_a::load_policy();
    let manifest = fold_a::resolve_manifest(&policy);
    let marks = fold_a::load_watermarks(&manifest);
    let nonces = fold_a::load_nonces(&manifest);
    let revocations = skim_sieve::load_ledger();
    let profiles = skim_fold::load_profiles();
    let matrix = skim_fold::load_matrix();

    let mut pending: Vec<skim_fold::Frame> = Vec::new();
    let mut quarantine: Vec<emit_c::QuarantineEntry> = Vec::new();

    let cred_dir = Path::new(lattice_core::CREDENTIALS_DIR);
    for lane_name in &["mqtt", "lora", "uart", "canbus", "zigbee"] {
        let path = cred_dir.join(format!("{}.jsonl", lane_name));
        if path.exists() {
            pending.extend(skim_fold::load_jsonl_lane(&path, lane_name));
        }
    }

    let wal_dir = Path::new(lattice_core::SEGMENTS_DIR);
    if let Ok(entries) = fs::read_dir(&wal_dir) {
        let mut paths: Vec<_> = entries
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().map_or(false, |ext| ext == "bin"))
            .collect();
        paths.sort();
        for path in paths {
            let Ok(raw) = fs::read(&path) else { continue };
            let (accepted, rejected) = sieve_b::decode_wal_with_quarantine(&raw, &nonces);
            quarantine.extend(rejected);
            pending.extend(accepted);
        }
    }

    // Interleave JSONL ∪ WAL by ascending timestamp within each epoch-and-lane stream.
    pending.sort_by(|a, b| {
        (a.epoch, a.lane.as_str(), a.ts, !a.from_wal).cmp(&(
            b.epoch,
            b.lane.as_str(),
            b.ts,
            !b.from_wal,
        ))
    });

    let mut all_frames: Vec<skim_fold::Frame> = Vec::new();
    let mut max_ts: HashMap<(u16, String), u64> = HashMap::new();
    if policy.replay_protection == "monotonic" {
        for f in pending {
            let key = (f.epoch, f.lane.clone());
            let prev = max_ts.get(&key).copied().unwrap_or(0);
            if prev > 0 && f.ts <= prev {
                if f.from_wal {
                    quarantine.push(emit_c::QuarantineEntry {
                        epoch: f.epoch,
                        lane: f.lane.clone(),
                        ts: f.ts,
                        reason: "replay".to_string(),
                    });
                }
            } else {
                max_ts.insert(key, f.ts);
                all_frames.push(f);
            }
        }
    } else {
        all_frames = pending;
    }

    let filtered: Vec<skim_fold::Frame> = all_frames
        .into_iter()
        .filter(|f| {
            let mark = marks.get(&f.epoch).copied().unwrap_or(0);
            f.ts <= mark
        })
        .collect();

    let classified = skim_sieve::classify(&filtered, &revocations);
    for cf in &classified {
        if cf.status == skim_sieve::FrameStatus::Revoked && cf.from_wal {
            quarantine.push(emit_c::QuarantineEntry {
                epoch: cf.epoch,
                lane: cf.lane.clone(),
                ts: cf.ts,
                reason: "revoked".to_string(),
            });
        }
    }

    let roster = skim_fold::evaluate(&classified, &profiles, &matrix);

    if let Err(e) = emit_c::write_roster(out, &roster) {
        eprintln!("emit failed: {e}");
        std::process::exit(1);
    }

    let quarantine_path = out.replace("ceremony-ledger", "quarantine");
    let quarantine_path = if quarantine_path == *out {
        let p = Path::new(out).parent().unwrap_or(Path::new("/output"));
        p.join("quarantine.json").to_string_lossy().into_owned()
    } else {
        quarantine_path
    };
    if let Err(e) = emit_c::write_quarantine(&quarantine_path, &quarantine) {
        eprintln!("quarantine emit failed: {e}");
        std::process::exit(1);
    }
}

fn parse_out(args: &[String]) -> Option<String> {
    args.windows(2)
        .find(|w| w[0] == "--out")
        .map(|w| w[1].clone())
}
EOF

# Fix 4: Emit — every quarantine entry (no epoch/lane dedupe)
cat > /app/vfy/src/emit_c.rs << 'EOF'
use std::fs;
use std::io;
use std::path::Path;

use crate::skim_fold::Roster;

pub struct QuarantineEntry {
    pub epoch: u16,
    pub lane: String,
    pub ts: u64,
    pub reason: String,
}

pub fn write_roster(path: &str, roster: &Roster) -> io::Result<()> {
    if path.trim().is_empty() {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "empty path"));
    }
    if let Some(parent) = Path::new(path).parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }
    let mut body = String::from("{\n  \"version\": 1,\n  \"backends\": [\n");
    for (i, (name, status)) in roster.backends.iter().enumerate() {
        if i > 0 {
            body.push_str(",\n");
        }
        body.push_str(&format!(
            "    {{\"name\": \"{}\", \"status\": \"{}\"}}",
            escape(name),
            escape(status)
        ));
    }
    body.push_str("\n  ],\n  \"epochs\": [\n");
    for (i, (id, profile, accepted)) in roster.epochs.iter().enumerate() {
        if i > 0 {
            body.push_str(",\n");
        }
        body.push_str(&format!(
            "    {{\"id\": {}, \"profile\": \"{}\", \"accepted\": {}}}",
            id,
            escape(profile),
            accepted
        ));
    }
    body.push_str("\n  ]\n}\n");
    fs::write(path, body)
}

pub fn write_quarantine(path: &str, entries: &[QuarantineEntry]) -> io::Result<()> {
    if path.trim().is_empty() {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "empty path"));
    }
    if let Some(parent) = Path::new(path).parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }
    let mut body = String::from("{\n  \"version\": 1,\n  \"rejected\": [\n");
    for (i, e) in entries.iter().enumerate() {
        if i > 0 {
            body.push_str(",\n");
        }
        body.push_str(&format!(
            "    {{\"epoch\": {}, \"lane\": \"{}\", \"ts\": {}, \"reason\": \"{}\"}}",
            e.epoch,
            escape(&e.lane),
            e.ts,
            escape(&e.reason)
        ));
    }
    body.push_str("\n  ]\n}\n");
    fs::write(path, body)
}

fn escape(raw: &str) -> String {
    raw.replace('\\', "\\\\").replace('"', "\\\"")
}
EOF

# Fix 5+6: co-presence polarity and hold threshold (surgical)
python3 -c '
from pathlib import Path
fold = Path("/app/vfy/src/skim_fold.rs")
ft = fold.read_text()
ft = ft.replace("|| f.status == FrameStatus::Revoked)", "|| f.status == FrameStatus::Held)")
fold.write_text(ft)
sieve = Path("/app/vfy/src/skim_sieve.rs")
st = sieve.read_text()
st = st.replace("f.ts >= r.after_ts", "f.ts > r.after_ts")
sieve.write_text(st)
'

# Build and attest
cd /app
cargo build -p trusteval --release
/app/target/release/trusteval attest --out /output/ceremony-ledger.json

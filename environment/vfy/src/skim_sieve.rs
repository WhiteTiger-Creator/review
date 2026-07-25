use std::fs;
use std::path::Path;

use crate::skim_fold::Frame;

pub struct Revocation {
    pub epoch: u16,
    pub lane: String,
    pub rtype: String,
    pub after_ts: u64,
}

#[derive(Clone)]
pub struct ClassifiedFrame {
    pub epoch: u16,
    pub lane: String,
    pub ts: u64,
    pub status: FrameStatus,
    pub from_wal: bool,
}

#[derive(Clone, PartialEq)]
pub enum FrameStatus {
    Active,
    Held,
    Revoked,
}

pub fn load_ledger() -> Vec<Revocation> {
    let path = Path::new(lattice_core::DATA_ROOT).join("ledger").join("revocations.jsonl");
    let Ok(text) = fs::read_to_string(&path) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for line in text.lines() {
        let t = line.trim();
        if t.is_empty() {
            continue;
        }
        let epoch = extract_json_u16(t, "\"epoch\":").unwrap_or(0);
        let lane = extract_json_str(t, "\"lane\":").unwrap_or_default();
        let rtype = extract_json_str(t, "\"type\":").unwrap_or_default();
        let after_ts = extract_json_u64(t, "\"after_ts\":").unwrap_or(0);
        out.push(Revocation { epoch, lane, rtype, after_ts });
    }
    out
}

pub fn classify(frames: &[Frame], revocations: &[Revocation]) -> Vec<ClassifiedFrame> {
    frames
        .iter()
        .map(|f| {
            let mut status = if f.hold {
                FrameStatus::Held
            } else {
                FrameStatus::Active
            };
            for r in revocations {
                if r.epoch == f.epoch && r.lane == f.lane && f.ts >= r.after_ts {
                    status = match r.rtype.as_str() {
                        "revoke" => FrameStatus::Revoked,
                        "hold" => FrameStatus::Held,
                        _ => status,
                    };
                }
            }
            ClassifiedFrame {
                epoch: f.epoch,
                lane: f.lane.clone(),
                ts: f.ts,
                status,
                from_wal: f.from_wal,
            }
        })
        .collect()
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

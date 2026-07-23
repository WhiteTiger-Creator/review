use crate::err::{KitErr, Result};
use crate::support::shape_u5::{SlotRec, StageHeap};
use serde::Deserialize;
use std::fs;
use std::path::Path;

#[derive(Deserialize)]
struct PackFile {
    rows: Vec<PackRow>,
}

#[derive(Deserialize)]
struct PackRow {
    tid: u64,
    raw_p: f64,
    blob_hex: String,
}

fn decode_hex(s: &str) -> Result<Vec<u8>> {
    if s.len() % 2 != 0 {
        return Err(KitErr::Parse("odd hex".into()));
    }
    let mut out = Vec::with_capacity(s.len() / 2);
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        let hi = from_hex(bytes[i])?;
        let lo = from_hex(bytes[i + 1])?;
        out.push((hi << 4) | lo);
        i += 2;
    }
    Ok(out)
}

fn from_hex(b: u8) -> Result<u8> {
    match b {
        b'0'..=b'9' => Ok(b - b'0'),
        b'a'..=b'f' => Ok(b - b'a' + 10),
        b'A'..=b'F' => Ok(b - b'A' + 10),
        _ => Err(KitErr::Parse("bad hex".into())),
    }
}

pub fn load_pack(path: &Path, alpha: f64, era: u64) -> Result<StageHeap> {
    let text = fs::read_to_string(path).map_err(|e| KitErr::Io(e.to_string()))?;
    let pack: PackFile = serde_json::from_str(&text).map_err(|e| KitErr::Parse(e.to_string()))?;
    let mut slots = Vec::with_capacity(pack.rows.len());
    for row in pack.rows {
        let blob = decode_hex(&row.blob_hex)?;
        let mass = row.raw_p.powf(alpha);
        slots.push(SlotRec {
            tid: row.tid,
            mass,
            stage_mass: mass,
            raw_p: row.raw_p,
            blob,
            era,
        });
    }
    Ok(StageHeap { slots, schema: 1 })
}

#!/usr/bin/env bash
set -euo pipefail
python3 <<'PYINNER'
from pathlib import Path
Path("/app/environment/flint/src/flint_sift.rs").write_text("""mod flat_sift;
pub use flat_sift::FlatSift;

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TraceRow {
    pub rid: String,
    pub aid: String,
    pub step: u32,
    pub eta: f64,
    pub vis: f64,
    pub halt: String,
    pub nest: String,
    pub lr0: f64,
    pub gamma: f64,
    pub period: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SideRow {
    pub rid: String,
    pub true_vis: f64,
    pub hid: u8,
}

#[derive(Clone, Debug, Default)]
pub struct SideBag {
    pub rows: Vec<SideRow>,
}

#[derive(Clone, Debug)]
pub struct SiftRow {
    pub rid: String,
    pub aid: String,
    pub step: u32,
    pub eta: f64,
    pub score: f64,
    pub halted: bool,
    pub from_side: bool,
    pub nest: String,
    pub lr0: f64,
    pub gamma: f64,
    pub period: u32,
}

#[derive(Clone, Debug, Default)]
pub struct SiftOut {
    pub rows: Vec<SiftRow>,
}

fn halt_flag(tag: &str) -> bool {
    let t = tag.trim().to_ascii_lowercase();
    matches!(t.as_str(), "e" | "cut" | "halted")
}

pub struct FlintSift;

impl FlintSift {
    pub fn reconcile(rows: &[TraceRow], side: &SideBag) -> SiftOut {
        let mut side_map: HashMap<String, &SideRow> = HashMap::new();
        for s in &side.rows {
            side_map.insert(s.rid.clone(), s);
        }
        let mut out = Vec::new();
        for r in rows {
            let mut score = r.vis;
            let mut from_side = false;
            if let Some(s) = side_map.get(&r.rid) {
                if s.hid == 1 {
                    score = s.true_vis;
                    from_side = true;
                }
            }
            out.push(SiftRow {
                rid: r.rid.clone(),
                aid: r.aid.clone(),
                step: r.step,
                eta: r.eta,
                score,
                halted: halt_flag(&r.halt),
                from_side,
                nest: r.nest.clone(),
                lr0: r.lr0,
                gamma: r.gamma,
                period: r.period,
            });
        }
        out.sort_by(|a, b| a.aid.cmp(&b.aid).then(a.step.cmp(&b.step)).then(a.rid.cmp(&b.rid)));
        SiftOut { rows: out }
    }
}


pub fn sift_rows(rows: &[TraceRow], side: &SideBag) -> SiftOut {
    FlintSift::reconcile(rows, side)
}
""")
PYINNER

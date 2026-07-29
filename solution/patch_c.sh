#!/usr/bin/env bash
set -euo pipefail
python3 <<'PYINNER'
from pathlib import Path
Path("/app/environment/kiln/src/kiln_forge.rs").write_text("""mod kiln_snap;
pub use kiln_snap::KilnSnap;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use crate::slag_bind::BindOut;

#[derive(Clone, Debug, Deserialize)]
pub struct ForgeBag {
    pub bag_id: String,
    pub knob: u64,
    pub salt: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct SheetArm {
    pub aid: String,
    pub rung_total: f64,
    pub lr0: f64,
    pub gamma: f64,
    pub period: u32,
    pub nest_outer: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct RungSheet {
    pub version: u32,
    pub arms: Vec<SheetArm>,
    pub best_aid: String,
    pub sheet_digest: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct LedgerCase {
    pub rid: String,
    pub aid: String,
    pub score_used: f64,
    pub from_side: bool,
    pub nest_outer: String,
    pub nest_inner: String,
    pub halted: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ForgeBlock {
    pub bag_id: String,
    pub aid: String,
    pub score: f64,
    pub nest_outer: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct AlignLedger {
    pub version: u32,
    pub cases: Vec<LedgerCase>,
    pub ledger_digest: String,
    pub forge: ForgeBlock,
}

#[derive(Clone, Debug)]
pub struct ForgeOut {
    pub sheet: RungSheet,
    pub ledger: AlignLedger,
}

fn hex_sha256(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

fn forge_score(aid: &str, lr0: f64, gamma: f64, period: u32, bag: &ForgeBag, nest_outer: &str) -> f64 {
    let s = format!(
        "{}|{:.10}|{:.10}|{}|{}|{}|{}",
        aid, lr0, gamma, period, bag.knob, bag.salt, nest_outer
    );
    let dig = Sha256::digest(s.as_bytes());
    let mut buf = [0u8; 8];
    buf.copy_from_slice(&dig[..8]);
    let v = u64::from_be_bytes(buf);
    (v as f64) / (u64::MAX as f64)
}

pub struct KilnForge;

impl KilnForge {
    pub fn cast(bind: BindOut, bag: &ForgeBag) -> ForgeOut {
        let mut arms: Vec<SheetArm> = bind
            .arms
            .iter()
            .map(|a| SheetArm {
                aid: a.aid.clone(),
                rung_total: a.rung_total,
                lr0: a.lr0,
                gamma: a.gamma,
                period: a.period,
                nest_outer: a.nest_outer.clone(),
            })
            .collect();
        arms.sort_by(|a, b| a.aid.cmp(&b.aid));
        let mut sheet_blob = String::new();
        for a in &arms {
            sheet_blob.push_str(&format!(
                "aid={};rung={:.10};lr0={:.10};gamma={:.10};period={};outer={}\n",
                a.aid, a.rung_total, a.lr0, a.gamma, a.period, a.nest_outer
            ));
        }
        let sheet_digest = hex_sha256(sheet_blob.as_bytes());

        let mut cases: Vec<LedgerCase> = Vec::new();
        for r in &bind.cases {
            let (outer, inner) = match bind.nest.get(&r.nest) {
                Some(e) => (e.outer.clone(), e.inner.clone()),
                None => (String::new(), String::new()),
            };
            cases.push(LedgerCase {
                rid: r.rid.clone(),
                aid: r.aid.clone(),
                score_used: r.score,
                from_side: r.from_side,
                nest_outer: outer,
                nest_inner: inner,
                halted: r.halted,
            });
        }
        cases.sort_by(|a, b| a.rid.cmp(&b.rid));
        let mut led_blob = String::new();
        for c in &cases {
            led_blob.push_str(&format!(
                "rid={};score={:.10};side={};outer={};inner={};halt={}\n",
                c.rid,
                c.score_used,
                if c.from_side { 1 } else { 0 },
                c.nest_outer,
                c.nest_inner,
                if c.halted { 1 } else { 0 }
            ));
        }
        let ledger_digest = hex_sha256(led_blob.as_bytes());

        let best = bind
            .arms
            .iter()
            .find(|a| a.aid == bind.best_aid)
            .cloned();
        let (score, nest_outer) = match best {
            Some(a) => (
                forge_score(&a.aid, a.lr0, a.gamma, a.period, bag, &a.nest_outer),
                a.nest_outer,
            ),
            None => (0.0, String::new()),
        };

        ForgeOut {
            sheet: RungSheet {
                version: 1,
                arms,
                best_aid: bind.best_aid.clone(),
                sheet_digest,
            },
            ledger: AlignLedger {
                version: 1,
                cases,
                ledger_digest,
                forge: ForgeBlock {
                    bag_id: bag.bag_id.clone(),
                    aid: bind.best_aid,
                    score,
                    nest_outer,
                },
            },
        }
    }
}


pub fn cast_bag(bind: BindOut, bag: &ForgeBag) -> ForgeOut {
    KilnForge::cast(bind, bag)
}
""")
PYINNER

mod kiln_snap;
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
        let sheet_digest = format!("{:x}", Sha256::digest(bind.best_aid.as_bytes()));
        let mut cases: Vec<LedgerCase> = bind
            .cases
            .iter()
            .map(|r| LedgerCase {
                rid: r.rid.clone(),
                aid: r.aid.clone(),
                score_used: r.score,
                from_side: r.from_side,
                nest_outer: "X".to_string(),
                nest_inner: "Y".to_string(),
                halted: r.halted,
            })
            .collect();
        cases.sort_by(|a, b| a.rid.cmp(&b.rid));
        let ledger_digest = format!("{:x}", Sha256::digest(b"smoke"));
        let score = (bag.knob as f64) / 1000.0;
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
                    nest_outer: "X".to_string(),
                },
            },
        }
    }
}


pub fn cast_bag(bind: BindOut, bag: &ForgeBag) -> ForgeOut {
    KilnForge::cast(bind, bag)
}

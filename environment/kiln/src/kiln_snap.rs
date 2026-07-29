use super::{AlignLedger, ForgeBag, ForgeBlock, ForgeOut, LedgerCase, RungSheet, SheetArm};
use crate::slag_bind::BindOut;

pub struct KilnSnap;

impl KilnSnap {
    /// Smoke helper: nest-blind cast; drops outer/inner on ledger rows.
    pub fn cast(bind: BindOut, bag: &ForgeBag) -> ForgeOut {
        let arms: Vec<SheetArm> = bind
            .arms
            .iter()
            .map(|a| SheetArm {
                aid: a.aid.clone(),
                rung_total: a.rung_total,
                lr0: a.lr0,
                gamma: a.gamma,
                period: a.period,
                nest_outer: String::new(),
            })
            .collect();
        let cases: Vec<LedgerCase> = bind
            .cases
            .iter()
            .map(|r| LedgerCase {
                rid: r.rid.clone(),
                aid: r.aid.clone(),
                score_used: r.score,
                from_side: false,
                nest_outer: String::new(),
                nest_inner: String::new(),
                halted: r.halted,
            })
            .collect();
        ForgeOut {
            sheet: RungSheet {
                version: 1,
                arms,
                best_aid: bind.best_aid.clone(),
                sheet_digest: "snap".to_string(),
            },
            ledger: AlignLedger {
                version: 1,
                cases,
                ledger_digest: "snap".to_string(),
                forge: ForgeBlock {
                    bag_id: bag.bag_id.clone(),
                    aid: bind.best_aid,
                    score: 0.0,
                    nest_outer: String::new(),
                },
            },
        }
    }
}

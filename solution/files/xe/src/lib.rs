use cartograph_core::{Campaign, Dungeon};
use reach_graph::{evaluate_reach, ReachReport};
use xa::{eval_xa, RepA};
use xb::{eval_xb, RepB};
use xc::{eval_xc, RepC};

#[derive(Clone, Debug)]
pub struct FairnessReport {
    pub ok: bool,
    pub reach: ReachReport,
    pub pace: RepA,
    pub trove: RepB,
    pub threat: RepC,
}

fn all_ok(reach: &ReachReport, pace: &RepA, trove: &RepB, threat: &RepC) -> bool {
    reach.ok && pace.ok && trove.ok && threat.ok
}

pub fn evaluate_fairness(camp: &Campaign, dung: &Dungeon) -> FairnessReport {
    let reach = evaluate_reach(camp, dung);
    let pace = eval_xa(camp, dung);
    let trove = eval_xb(camp, dung);
    let threat = eval_xc(camp, dung);
    let ok = all_ok(&reach, &pace, &trove, &threat);
    FairnessReport {
        ok,
        reach,
        pace,
        trove,
        threat,
    }
}

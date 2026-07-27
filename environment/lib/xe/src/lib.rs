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

pub fn evaluate_fairness(camp: &Campaign, dung: &Dungeon) -> FairnessReport {
    let reach = evaluate_reach(camp, dung);
    // Provisional gates only — threat is computed for metrics but omitted from ok.
    let pace = if reach.ok {
        eval_xa(camp, dung)
    } else {
        RepA {
            ok: false,
            mean_gap: 0.0,
        }
    };
    let trove = if pace.ok {
        eval_xb(camp, dung)
    } else {
        RepB {
            ok: false,
            densities: [0.0, 0.0, 0.0],
            total_gold: 0,
        }
    };
    let threat = eval_xc(camp, dung);
    let ok = reach.ok && pace.ok && trove.ok;
    FairnessReport {
        ok,
        reach,
        pace,
        trove,
        threat,
    }
}

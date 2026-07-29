mod flat_sift;
pub use flat_sift::FlatSift;

use serde::{Deserialize, Serialize};

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

pub struct FlintSift;

impl FlintSift {
    pub fn reconcile(rows: &[TraceRow], _side: &SideBag) -> SiftOut {
        let mut out = Vec::new();
        for r in rows {
            out.push(SiftRow {
                rid: r.rid.clone(),
                aid: r.aid.clone(),
                step: r.step,
                eta: r.eta,
                score: r.vis,
                halted: r.halt == "halted",
                from_side: false,
                nest: r.nest.clone(),
                lr0: r.lr0,
                gamma: r.gamma,
                period: r.period,
            });
        }
        SiftOut { rows: out }
    }
}


pub fn sift_rows(rows: &[TraceRow], side: &SideBag) -> SiftOut {
    FlintSift::reconcile(rows, side)
}

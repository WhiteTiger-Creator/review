use super::{ArmBind, BindOut, GridSpec, NestMap};
use crate::flint_sift::{SiftOut, SiftRow};

pub struct SlagSumm;

impl SlagSumm {
    /// Smoke helper: copies max visible score per aid with no nest binding.
    pub fn bind(sift: SiftOut, _grid: &GridSpec, _nest: &NestMap) -> BindOut {
        let mut best: Option<SiftRow> = None;
        for r in sift.rows {
            best = Some(match best {
                None => r,
                Some(b) if r.score > b.score => r,
                Some(b) => b,
            });
        }
        let mut arms = Vec::new();
        let mut best_aid = String::new();
        let mut cases = Vec::new();
        if let Some(r) = best {
            best_aid = r.aid.clone();
            cases.push(r.clone());
            arms.push(ArmBind {
                aid: r.aid.clone(),
                rung_total: r.score,
                lr0: r.lr0,
                gamma: r.gamma,
                period: r.period,
                nest_outer: r.nest.clone(),
                halt_done: false,
            });
        }
        BindOut {
            arms,
            best_aid,
            cases,
            nest: NestMap::new(),
        }
    }
}

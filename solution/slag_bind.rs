mod slag_summ;
pub use slag_summ::SlagSumm;

use crate::flint_sift::{SiftOut, SiftRow};
use serde::Deserialize;
use std::collections::HashMap;

#[derive(Clone, Debug, Deserialize)]
pub struct GridTriple {
    pub lr0: f64,
    pub gamma: f64,
    pub period: u32,
}

#[derive(Clone, Debug, Deserialize)]
pub struct GridSpec {
    pub triples: Vec<GridTriple>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct NestEntry {
    pub outer: String,
    pub inner: String,
}

pub type NestMap = HashMap<String, NestEntry>;

#[derive(Clone, Debug)]
pub struct ArmBind {
    pub aid: String,
    pub rung_total: f64,
    pub lr0: f64,
    pub gamma: f64,
    pub period: u32,
    pub nest_outer: String,
    pub halt_done: bool,
}

#[derive(Clone, Debug, Default)]
pub struct BindOut {
    pub arms: Vec<ArmBind>,
    pub best_aid: String,
    pub cases: Vec<SiftRow>,
    pub nest: NestMap,
}

const TOL: f64 = 1e-9;

fn eta_expected(lr0: f64, gamma: f64, period: u32, step: u32) -> f64 {
    let p = if period == 0 { 1 } else { period };
    lr0 * gamma.powi((step / p) as i32)
}

fn near(a: f64, b: f64) -> bool {
    (a - b).abs() <= TOL
}

pub struct SlagBind;

impl SlagBind {
    pub fn bind(sift: SiftOut, grid: &GridSpec, nest: &NestMap) -> BindOut {
        let mut by_aid: HashMap<String, Vec<SiftRow>> = HashMap::new();
        for r in sift.rows {
            by_aid.entry(r.aid.clone()).or_default().push(r);
        }
        let mut arms = Vec::new();
        let mut cases = Vec::new();
        for (aid, rows) in by_aid {
            let mut outer_counts: HashMap<String, u32> = HashMap::new();
            for r in &rows {
                if let Some(e) = nest.get(&r.nest) {
                    *outer_counts.entry(e.outer.clone()).or_default() += 1;
                }
            }
            if outer_counts.is_empty() {
                continue;
            }
            let mode_outer = outer_counts
                .into_iter()
                .max_by(|a, b| a.1.cmp(&b.1).then_with(|| b.0.cmp(&a.0)))
                .map(|(k, _)| k)
                .unwrap();
            let mut kept: Vec<SiftRow> = Vec::new();
            for r in rows {
                match nest.get(&r.nest) {
                    Some(e) if e.outer == mode_outer => kept.push(r),
                    _ => {}
                }
            }
            if kept.is_empty() {
                continue;
            }
            kept.sort_by(|a, b| a.step.cmp(&b.step).then(a.rid.cmp(&b.rid)));
            let lr0 = kept[0].lr0;
            let gamma = kept[0].gamma;
            let period = kept[0].period;
            if kept.iter().any(|r| !near(r.lr0, lr0) || !near(r.gamma, gamma) || r.period != period)
            {
                continue;
            }
            let grid_ok = grid.triples.iter().any(|t| {
                near(t.lr0, lr0) && near(t.gamma, gamma) && t.period == period
            });
            if !grid_ok {
                continue;
            }
            let mut ok_eta = true;
            for r in &kept {
                if !near(r.eta, eta_expected(lr0, gamma, period, r.step)) {
                    ok_eta = false;
                    break;
                }
            }
            if !ok_eta {
                continue;
            }
            let p = if period == 0 { 1 } else { period };
            let mut rung_total = 0.0;
            for r in &kept {
                if r.step % p == 0 {
                    rung_total += r.score;
                }
            }
            let halt_done = kept.last().map(|r| r.halted).unwrap_or(false);
            for r in &kept {
                cases.push(r.clone());
            }
            arms.push(ArmBind {
                aid,
                rung_total,
                lr0,
                gamma,
                period,
                nest_outer: mode_outer,
                halt_done,
            });
        }
        arms.sort_by(|a, b| a.aid.cmp(&b.aid));
        cases.sort_by(|a, b| a.rid.cmp(&b.rid));
        let best_aid = arms
            .iter()
            .filter(|a| !a.halt_done)
            .max_by(|a, b| {
                a.rung_total
                    .partial_cmp(&b.rung_total)
                    .unwrap_or(std::cmp::Ordering::Equal)
                    .then_with(|| b.aid.cmp(&a.aid))
            })
            .map(|a| a.aid.clone())
            .unwrap_or_default();
        BindOut {
            arms,
            best_aid,
            cases,
            nest: nest.clone(),
        }
    }
}


pub fn bind_rows(sift: SiftOut, grid: &GridSpec, nest: &NestMap) -> BindOut {
    SlagBind::bind(sift, grid, nest)
}

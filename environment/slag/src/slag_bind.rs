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

pub struct SlagBind;

impl SlagBind {
    pub fn bind(sift: SiftOut, _grid: &GridSpec, nest: &NestMap) -> BindOut {
        let mut by_aid: HashMap<String, Vec<SiftRow>> = HashMap::new();
        for r in sift.rows {
            by_aid.entry(r.aid.clone()).or_default().push(r);
        }
        let mut arms = Vec::new();
        let mut cases = Vec::new();
        for (aid, rows) in by_aid {
            let mut total = 0.0;
            for r in &rows {
                total += r.score;
                cases.push(r.clone());
            }
            let lr0 = rows.first().map(|r| r.lr0).unwrap_or(0.0);
            let gamma = rows.first().map(|r| r.gamma).unwrap_or(0.0);
            let period = rows.first().map(|r| r.period).unwrap_or(1);
            arms.push(ArmBind {
                aid,
                rung_total: total,
                lr0,
                gamma,
                period,
                nest_outer: "ALL".to_string(),
                halt_done: false,
            });
        }
        arms.sort_by(|a, b| a.aid.cmp(&b.aid));
        let best_aid = arms
            .iter()
            .max_by(|a, b| {
                a.rung_total
                    .partial_cmp(&b.rung_total)
                    .unwrap_or(std::cmp::Ordering::Equal)
                    .then_with(|| b.aid.cmp(&a.aid))
            })
            .map(|a| a.aid.clone())
            .unwrap_or_default();
        let _ = nest;
        BindOut {
            arms,
            best_aid,
            cases,
            nest: NestMap::new(),
        }
    }
}


pub fn bind_rows(sift: SiftOut, grid: &GridSpec, nest: &NestMap) -> BindOut {
    SlagBind::bind(sift, grid, nest)
}

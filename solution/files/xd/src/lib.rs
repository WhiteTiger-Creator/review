use cartograph_core::{generate_dungeon, Campaign, Dungeon};
use xe::{evaluate_fairness, FairnessReport};

#[derive(Clone, Debug)]
pub struct HuntResult {
    pub seed: u64,
    pub dungeon: Dungeon,
    pub report: FairnessReport,
}

fn window_end(camp: &Campaign) -> u64 {
    camp.search_origin.saturating_add(camp.search_limit)
}

fn try_seed(camp: &Campaign, seed: u64) -> Option<HuntResult> {
    let dungeon = generate_dungeon(camp, seed);
    let report = evaluate_fairness(camp, &dungeon);
    if report.ok {
        Some(HuntResult {
            seed,
            dungeon,
            report,
        })
    } else {
        None
    }
}

pub fn scan_xd(camp: &Campaign) -> Option<HuntResult> {
    let start = camp.search_origin;
    let end = window_end(camp);
    for seed in start..end {
        if let Some(hit) = try_seed(camp, seed) {
            return Some(hit);
        }
    }
    None
}

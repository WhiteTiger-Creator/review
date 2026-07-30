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

pub fn scan_xd(camp: &Campaign) -> Option<HuntResult> {
    let start = camp.search_origin;
    let end = window_end(camp);
    let mut last: Option<HuntResult> = None;
    for seed in start..end {
        let dungeon = generate_dungeon(camp, seed);
        let report = evaluate_fairness(camp, &dungeon);
        if report.ok {
            last = Some(HuntResult {
                seed,
                dungeon,
                report,
            });
        }
    }
    last
}

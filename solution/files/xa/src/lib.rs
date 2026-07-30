use cartograph_core::{Campaign, Dungeon};

#[derive(Clone, Debug)]
pub struct RepA {
    pub ok: bool,
    pub mean_gap: f64,
}

fn collect_monster_indices(dung: &Dungeon) -> Vec<usize> {
    dung.critical_path
        .iter()
        .enumerate()
        .filter_map(|(i, &rid)| {
            if dung.rooms[rid].threat > 0 {
                Some(i)
            } else {
                None
            }
        })
        .collect()
}

fn pairwise_gaps(indices: &[usize]) -> Vec<u32> {
    let mut gaps = Vec::new();
    for pair in indices.windows(2) {
        gaps.push((pair[1] - pair[0]) as u32);
    }
    gaps
}

fn mean_u32(values: &[u32]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.iter().map(|g| f64::from(*g)).sum::<f64>() / values.len() as f64
}

fn gaps_meet_min(gaps: &[u32], min_gap: u32) -> bool {
    gaps.iter().all(|g| *g >= min_gap)
}

pub fn eval_xa(camp: &Campaign, dung: &Dungeon) -> RepA {
    let monster_idx = collect_monster_indices(dung);
    if monster_idx.is_empty() {
        return RepA {
            ok: false,
            mean_gap: 0.0,
        };
    }
    if monster_idx.len() == 1 {
        return RepA {
            ok: true,
            mean_gap: camp.mean_gap_min,
        };
    }
    let gaps = pairwise_gaps(&monster_idx);
    let mean_gap = mean_u32(&gaps);
    let ok = gaps_meet_min(&gaps, camp.min_gap) && mean_gap >= camp.mean_gap_min;
    RepA { ok, mean_gap }
}

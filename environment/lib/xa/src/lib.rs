use cartograph_core::{Campaign, Dungeon};

#[derive(Clone, Debug)]
pub struct RepA {
    pub ok: bool,
    pub mean_gap: f64,
}

fn monster_path_indices(dung: &Dungeon) -> Vec<usize> {
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

pub fn eval_xa(camp: &Campaign, dung: &Dungeon) -> RepA {
    let monster_idx = monster_path_indices(dung);
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
    let mut gaps = Vec::new();
    let mut ok = true;
    for pair in monster_idx.windows(2) {
        let gap = (pair[1] - pair[0]) as u32;
        if gap <= camp.min_gap {
            ok = false;
        }
        gaps.push(gap);
    }
    let mean_gap = gaps.iter().map(|g| f64::from(*g)).sum::<f64>() / gaps.len() as f64;
    if mean_gap < camp.mean_gap_min {
        ok = false;
    }
    RepA { ok, mean_gap }
}

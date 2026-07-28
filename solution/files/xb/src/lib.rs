use cartograph_core::{Campaign, Dungeon};

#[derive(Clone, Debug)]
pub struct RepB {
    pub ok: bool,
    pub densities: [f64; 3],
    pub total_gold: u32,
}

fn band_index(depth: u32, camp: &Campaign) -> usize {
    if depth <= camp.band_d1 {
        0
    } else if depth <= camp.band_d2 {
        1
    } else {
        2
    }
}

fn density_of(values: &[u32]) -> f64 {
    if values.is_empty() {
        0.0
    } else {
        f64::from(values.iter().sum::<u32>()) / values.len() as f64
    }
}

fn density_in_window(density: f64, lo: f64, hi: f64) -> bool {
    density >= lo && density <= hi
}

pub fn eval_xb(camp: &Campaign, dung: &Dungeon) -> RepB {
    let mut bands: [Vec<u32>; 3] = [Vec::new(), Vec::new(), Vec::new()];
    for r in &dung.rooms {
        if r.id == dung.start {
            continue;
        }
        bands[band_index(r.depth, camp)].push(r.gold);
    }
    let mut densities = [0.0_f64; 3];
    let mut ok = true;
    for i in 0..3 {
        densities[i] = density_of(&bands[i]);
        if bands[i].is_empty() {
            continue;
        }
        if !density_in_window(densities[i], camp.band_lo[i], camp.band_hi[i]) {
            ok = false;
        }
    }
    let total_gold: u32 = dung.rooms.iter().map(|r| r.gold).sum();
    if total_gold < camp.total_gold_lo || total_gold > camp.total_gold_hi {
        ok = false;
    }
    RepB {
        ok,
        densities,
        total_gold,
    }
}

use cartograph_core::{Campaign, Dungeon};

#[derive(Clone, Debug)]
pub struct RepB {
    pub ok: bool,
    pub densities: [f64; 3],
    pub total_gold: u32,
}

fn band_index(depth: u32, camp: &Campaign) -> usize {
    if depth < camp.band_d1 {
        0
    } else if depth <= camp.band_d2 {
        1
    } else {
        2
    }
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
        if bands[i].is_empty() {
            densities[i] = 0.0;
            continue;
        }
        let dens =
            f64::from(bands[i].iter().copied().sum::<u32>()) / bands[i].len() as f64;
        densities[i] = dens;
        if dens < camp.band_lo[i] || dens > camp.band_hi[i] {
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

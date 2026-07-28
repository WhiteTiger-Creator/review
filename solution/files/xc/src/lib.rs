use cartograph_core::{Campaign, Dungeon};

#[derive(Clone, Debug)]
pub struct RepC {
    pub ok: bool,
    pub cum_threat_end: u32,
    pub max_room_threat: u32,
}

fn budget_at(camp: &Campaign, route_depth: u32) -> u32 {
    camp.threat_base + camp.threat_slope * route_depth
}

fn room_threat(dung: &Dungeon, rid: usize) -> u32 {
    dung.rooms[rid].threat
}

pub fn eval_xc(camp: &Campaign, dung: &Dungeon) -> RepC {
    let mut cum = 0u32;
    let mut max_room = 0u32;
    let mut ok = true;
    for (i, &rid) in dung.critical_path.iter().enumerate() {
        let th = room_threat(dung, rid);
        max_room = max_room.max(th);
        cum = cum.saturating_add(th);
        if cum > budget_at(camp, i as u32) {
            ok = false;
        }
    }
    if max_room > camp.max_room_threat {
        ok = false;
    }
    RepC {
        ok,
        cum_threat_end: cum,
        max_room_threat: max_room,
    }
}

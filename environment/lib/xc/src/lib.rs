use cartograph_core::{Campaign, Dungeon};

#[derive(Clone, Debug)]
pub struct RepC {
    pub ok: bool,
    pub cum_threat_end: u32,
    pub max_room_threat: u32,
}

pub fn eval_xc(camp: &Campaign, dung: &Dungeon) -> RepC {
    let mut cum = 0u32;
    let mut max_room = 0u32;
    for &rid in &dung.critical_path {
        let th = dung.rooms[rid].threat;
        max_room = max_room.max(th);
        cum = cum.saturating_add(th);
    }
    let end_i = dung.critical_path.len().saturating_sub(1) as u32;
    let end_budget = camp.threat_base + camp.threat_slope * end_i;
    let mut ok = cum <= end_budget;
    if max_room > camp.max_room_threat {
        ok = false;
    }
    RepC {
        ok,
        cum_threat_end: cum,
        max_room_threat: max_room,
    }
}

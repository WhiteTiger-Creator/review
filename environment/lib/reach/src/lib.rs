use cartograph_core::{Campaign, Dungeon};

#[derive(Clone, Debug)]
pub struct ReachReport {
    pub ok: bool,
    pub path_len: u32,
    pub reachable_rooms: usize,
}

pub fn evaluate_reach(camp: &Campaign, dung: &Dungeon) -> ReachReport {
    let n = dung.rooms.len();
    let reachable = dung.rooms.iter().filter(|r| r.depth < 999).count();
    let path_len = if dung.critical_path.is_empty() {
        0
    } else {
        (dung.critical_path.len() - 1) as u32
    };
    let exit_ok = dung.rooms.iter().any(|r| r.id == dung.exit && r.depth < 999);
    let ok = reachable == n
        && exit_ok
        && path_len >= camp.path_min
        && path_len <= camp.path_max;
    ReachReport {
        ok,
        path_len,
        reachable_rooms: reachable,
    }
}

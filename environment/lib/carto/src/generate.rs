
use undercroft_rng::XorShift64;

#[derive(Clone, Debug)]
pub struct Campaign {
    pub campaign_id: String,
    pub width: u32,
    pub height: u32,
    pub room_target: usize,
    pub chest_count: usize,
    pub monster_count: usize,
    pub path_min: u32,
    pub path_max: u32,
    pub min_gap: u32,
    pub mean_gap_min: f64,
    pub band_d1: u32,
    pub band_d2: u32,
    pub band_lo: [f64; 3],
    pub band_hi: [f64; 3],
    pub total_gold_lo: u32,
    pub total_gold_hi: u32,
    pub threat_base: u32,
    pub threat_slope: u32,
    pub max_room_threat: u32,
    pub search_origin: u64,
    pub search_limit: u64,
}

#[derive(Clone, Debug)]
pub struct Room {
    pub id: usize,
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
    pub depth: u32,
    pub gold: u32,
    pub threat: u32,
}

#[derive(Clone, Debug)]
pub struct Dungeon {
    pub rooms: Vec<Room>,
    pub edges: Vec<(usize, usize)>,
    pub start: usize,
    pub exit: usize,
    pub critical_path: Vec<usize>,
}

pub fn generate_dungeon(camp: &Campaign, seed: u64) -> Dungeon {
    let mut rng = XorShift64::new(seed);
    let mut rooms: Vec<Room> = Vec::new();
    let mut attempts = 0u32;
    while rooms.len() < camp.room_target && attempts < 5000 {
        attempts += 1;
        let w = 3 + (rng.next_u64() % 3) as i32;
        let h = 3 + (rng.next_u64() % 3) as i32;
        let max_x = (camp.width as i32 - w - 1).max(1);
        let max_y = (camp.height as i32 - h - 1).max(1);
        let x = 1 + (rng.next_u64() % max_x as u64) as i32;
        let y = 1 + (rng.next_u64() % max_y as u64) as i32;
        let mut ok = true;
        for o in &rooms {
            if !(x + w + 1 <= o.x
                || o.x + o.w + 1 <= x
                || y + h + 1 <= o.y
                || o.y + o.h + 1 <= y)
            {
                ok = false;
                break;
            }
        }
        if ok {
            let id = rooms.len();
            rooms.push(Room {
                id,
                x,
                y,
                w,
                h,
                depth: 0,
                gold: 0,
                threat: 0,
            });
        }
    }
    let n = rooms.len();
    let mut edge_set = std::collections::BTreeSet::new();
    let add_edge = |a: usize, b: usize, set: &mut std::collections::BTreeSet<(usize, usize)>| {
        if a != b {
            let e = if a < b { (a, b) } else { (b, a) };
            set.insert(e);
        }
    };
    for i in 1..n {
        add_edge(i - 1, i, &mut edge_set);
    }
    let extra = (n / 3).max(1);
    for _ in 0..extra {
        if n == 0 {
            break;
        }
        let a = (rng.next_u64() as usize) % n;
        let b = (rng.next_u64() as usize) % n;
        add_edge(a, b, &mut edge_set);
    }
    let edges: Vec<(usize, usize)> = edge_set.into_iter().collect();
    let mut adj = vec![Vec::new(); n];
    for &(a, b) in &edges {
        adj[a].push(b);
        adj[b].push(a);
    }
    let mut depth = vec![999u32; n];
    if n > 0 {
        let mut q = std::collections::VecDeque::new();
        depth[0] = 0;
        q.push_back(0usize);
        while let Some(u) = q.pop_front() {
            for &v in &adj[u] {
                if depth[v] == 999 {
                    depth[v] = depth[u] + 1;
                    q.push_back(v);
                }
            }
        }
    }
    for r in rooms.iter_mut() {
        r.depth = depth[r.id];
    }
    let start = 0usize;
    let exit = rooms
        .iter()
        .filter(|r| r.depth < 999)
        .max_by_key(|r| (r.depth, std::cmp::Reverse(r.id)))
        .map(|r| r.id)
        .unwrap_or(0);
    // tie: maximum depth, then lowest id — max_by_key with Reverse(id) gives lowest id on tie
    let candidates: Vec<usize> = rooms.iter().filter(|r| r.id != start).map(|r| r.id).collect();
    for _ in 0..camp.chest_count {
        if candidates.is_empty() {
            break;
        }
        let rid = candidates[(rng.next_u64() as usize) % candidates.len()];
        let gold = 10 + (rng.next_u64() % 40) as u32 + rooms[rid].depth * 5;
        rooms[rid].gold = rooms[rid].gold.saturating_add(gold);
    }
    for _ in 0..camp.monster_count {
        if candidates.is_empty() {
            break;
        }
        let rid = candidates[(rng.next_u64() as usize) % candidates.len()];
        let threat = 3 + (rng.next_u64() % 8) as u32 + rooms[rid].depth * 2;
        rooms[rid].threat = rooms[rid].threat.saturating_add(threat);
    }
    let mut parent = vec![None; n];
    let mut seen = vec![false; n];
    let mut q = std::collections::VecDeque::new();
    if n > 0 {
        seen[start] = true;
        q.push_back(start);
        while let Some(u) = q.pop_front() {
            for &v in &adj[u] {
                if !seen[v] {
                    seen[v] = true;
                    parent[v] = Some(u);
                    q.push_back(v);
                }
            }
        }
    }
    let mut path = Vec::new();
    if n > 0 && (seen[exit] || exit == start) {
        let mut cur = Some(exit);
        while let Some(c) = cur {
            path.push(c);
            cur = parent[c];
            if c == start {
                break;
            }
        }
        path.reverse();
    }
    Dungeon {
        rooms,
        edges,
        start,
        exit,
        critical_path: path,
    }
}

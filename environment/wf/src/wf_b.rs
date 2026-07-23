use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};

use m7q::{mode_tag, Row};
use n2v::{op_b, Graph};
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Deserialize)]
struct SiteRows {
    site_id: String,
    eta: f64,
    rows: Vec<RowData>,
}

#[derive(Deserialize, Clone)]
struct RowData {
    arm: u32,
    weight_tok: u32,
    mode: Vec<u8>,
}

impl From<RowData> for Row {
    fn from(r: RowData) -> Self {
        Self {
            arm: r.arm,
            weight_tok: r.weight_tok,
            mode: r.mode,
        }
    }
}

#[derive(Serialize)]
struct FoldSite {
    site_id: String,
    fold_digest: String,
    synth_obs: BTreeMap<String, i64>,
    obligation_count: i64,
}

#[derive(Deserialize)]
struct OrbitSpec {
    site: String,
    perm: Vec<usize>,
}

fn apply_perm(rows: &mut [RowData], perm: &[usize]) {
    if perm.len() != rows.len() {
        return;
    }
    let copy = rows.to_vec();
    for (dst, &src) in perm.iter().enumerate() {
        if src < copy.len() {
            rows[dst] = copy[src].clone();
        }
    }
}

fn score_rows(rows: &[Row], eta: f64) -> BTreeMap<String, i64> {
    let mut obs = BTreeMap::new();
    for r in rows {
        let w_prev = r.weight_tok as f64;
        let w_next = w_prev * (-eta * (r.weight_tok as f64) / 100.0).exp();
        obs.insert(r.arm.to_string(), (w_next / 10.0).round() as i64);
    }
    obs
}

fn closed_keys(conn: &Connection) -> HashSet<(u32, String)> {
    let mut stmt = conn.prepare("SELECT arm_id, mode_tag FROM arm_lineage").expect("keys");
    let mut set = HashSet::new();
    let rows = stmt
        .query_map([], |row| {
            Ok((row.get::<_, i64>(0)? as u32, row.get::<_, String>(1)?))
        })
        .expect("q");
    for r in rows {
        let (a, m) = r.expect("row");
        set.insert((a, mode_tag(m.as_bytes())));
    }
    set
}

fn obligation_count(rows: &[Row], closed: &HashSet<(u32, String)>) -> i64 {
    rows.iter()
        .filter(|r| !closed.contains(&(r.arm, mode_tag(&r.mode))))
        .count() as i64
}

fn catalog_digest(conn: &Connection) -> String {
    let mut stmt = conn
        .prepare("SELECT arm_id, mode_tag, lineage_seq, weight_base FROM arm_lineage ORDER BY arm_id, mode_tag")
        .expect("lineage");
    let mut lines = Vec::new();
    let rows = stmt
        .query_map([], |row| {
            Ok(format!(
                "{}|{}|{}|{}",
                row.get::<_, i64>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)?,
                row.get::<_, i64>(3)?
            ))
        })
        .expect("q");
    for r in rows {
        lines.push(r.expect("row"));
    }
    format!("{:x}", Sha256::digest(lines.join("\n").as_bytes()))
}

fn lineage_json(conn: &Connection) -> Vec<serde_json::Value> {
    let mut stmt = conn
        .prepare("SELECT arm_id, mode_tag, lineage_seq, weight_base FROM arm_lineage ORDER BY arm_id, mode_tag")
        .expect("lineage");
    let mut out = Vec::new();
    let rows = stmt
        .query_map([], |row| {
            Ok(serde_json::json!({
                "arm_id": row.get::<_, i64>(0)?,
                "mode_tag": row.get::<_, String>(1)?,
                "lineage_seq": row.get::<_, i64>(2)?,
                "weight_base": row.get::<_, i64>(3)?,
            }))
        })
        .expect("q");
    for r in rows {
        out.push(r.expect("row"));
    }
    out
}

fn replay_db(env_root: &Path) -> Connection {
    let conn = Connection::open(env_root.join("var/k9.db")).expect("db");
    for mig in ["001_init.sql", "002_arm.sql"] {
        let sql = fs::read_to_string(env_root.join("var/mig").join(mig)).expect("mig");
        conn.execute_batch(&sql).expect("mig");
    }
    conn
}

fn read_sched(path: &Path) -> (i64, f64) {
    let txt = fs::read_to_string(path).unwrap_or_default();
    for (i, line) in txt.lines().enumerate() {
        if i == 0 {
            continue;
        }
        let p: Vec<&str> = line.split('\t').collect();
        return (p[1].parse().unwrap_or(0), p[3].parse().unwrap_or(1.0));
    }
    (0, 1.0)
}

fn admission(obs: &BTreeMap<String, i64>, threshold: i64) -> String {
    if obs.values().copied().max().unwrap_or(0) >= threshold {
        "open".to_string()
    } else {
        "hold".to_string()
    }
}

fn main() {
    let mut site_root = PathBuf::from("/app/environment/k8");
    let mut rows_in = PathBuf::from("/tmp/wf_stage_a/rows.json");
    let mut out = PathBuf::from("/tmp/wf_stage_b/fold.json");
    let mut env_root = PathBuf::from("/app/environment");
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--site-root" => site_root = PathBuf::from(args.next().expect("site-root")),
            "--rows" => rows_in = PathBuf::from(args.next().expect("rows")),
            "--out" => out = PathBuf::from(args.next().expect("out")),
            "--env-root" => env_root = PathBuf::from(args.next().expect("env-root")),
            _ => {}
        }
    }
    let sites_in: Vec<SiteRows> = serde_json::from_str(&fs::read_to_string(rows_in).expect("read")).expect("json");
    let conn = replay_db(&env_root);
    let closed = closed_keys(&conn);
    let cat = catalog_digest(&conn);
    let lineage = lineage_json(&conn);

    let mut folded = Vec::new();
    for mut site in sites_in {
        if let Ok(rd) = fs::read_dir(site_root.join("_orbits")) {
            for ent in rd.flatten() {
                let p = ent.path();
                if p.extension().and_then(|s| s.to_str()) != Some("json") {
                    continue;
                }
                let spec: OrbitSpec =
                    serde_json::from_str(&fs::read_to_string(&p).expect("orb")).expect("orb");
                if spec.site == site.site_id {
                    apply_perm(&mut site.rows, &spec.perm);
                }
            }
        }
        let rust_rows: Vec<Row> = site.rows.iter().cloned().map(Row::from).collect();
        let graph = Graph {
            rows: rust_rows.clone(),
        };
        let fold = op_b(&graph, 0);
        let obs = score_rows(&rust_rows, site.eta);
        let (threshold, env_hi) = read_sched(&site_root.join(&site.site_id).join("schedule.tsv"));
        folded.push(serde_json::json!({
            "site_id": site.site_id,
            "fold_digest": fold.digest,
            "synth_obs": obs,
            "obligation_count": obligation_count(&rust_rows, &closed),
            "catalog_digest": cat,
            "admission": admission(&obs, threshold),
            "env_hi": env_hi,
            "lineage_rows": lineage,
        }));
    }
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent).expect("mkdir");
    }
    fs::write(out, serde_json::to_string_pretty(&folded).expect("json")).expect("write");
}


use pixilock_core::{
    inspect, read_csv, report_to_json, CascadePolicy, DepRow, Edge, PinRow,
};
use std::collections::{HashMap, HashSet};
use std::env;
use std::path::Path;
use std::process;

fn fail(msg: &str) -> ! {
    eprintln!("{msg}");
    process::exit(2);
}

fn main() {
    let mut args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() {
        fail("usage");
    }
    if args[0] == "--version" {
        println!("pixilock 12.6.3");
        return;
    }
    if args[0] != "inspect" {
        fail("unknown");
    }
    args.remove(0);
    let mut lane = String::new();
    let mut edges_p = String::new();
    let mut arts_p = String::new();
    let mut deps_p = String::new();
    let mut mirrors_p = String::new();
    let mut pins_p = String::new();
    let mut xor_p = String::new();
    let mut bans_p = String::new();
    let mut forb_p = String::new();
    let mut caps_p = String::new();
    let mut risk_p = String::new();
    let mut cascade_policy_p = String::new();
    let mut cascade_route_blocks_p = String::new();
    let mut hops = 0u32;
    let mut out = String::new();
    let mut i = 0;
    while i < args.len() {
        let a = args[i].clone();
        let v = args.get(i + 1).cloned().unwrap_or_default();
        match a.as_str() {
            "--lane" => lane = v,
            "--edges" => edges_p = v,
            "--artifacts" => arts_p = v,
            "--deps" => deps_p = v,
            "--mirrors" => mirrors_p = v,
            "--pins" => pins_p = v,
            "--xor" => xor_p = v,
            "--bans" => bans_p = v,
            "--forbidden-hosts" => forb_p = v,
            "--version-caps" => caps_p = v,
            "--risk-policy" => risk_p = v,
            "--cascade-policy" => cascade_policy_p = v,
            "--cascade-route-blocks" => cascade_route_blocks_p = v,
            "--retention-hops" => hops = v.parse().unwrap_or(0),
            "--out" => out = v,
            _ => fail(&format!("unknown {a}")),
        }
        i += 2;
    }
    if lane.is_empty() || out.is_empty() {
        fail("missing --lane/--out");
    }
    if risk_p.is_empty() {
        fail("missing --risk-policy");
    }
    if let Some(parent) = Path::new(&out).parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent).unwrap_or_else(|_| fail("mkdir --out parent"));
        }
    }

    let edge_rows = filter_lane(&read_csv(&edges_p).unwrap_or_else(|_| fail("edges")), &lane);
    let edges: Vec<Edge> = edge_rows
        .iter()
        .map(|r| Edge {
            parent: r[1].clone(),
            child: r[2].clone(),
            hard: r[3] == "hard",
        })
        .collect();
    let art_rows = filter_lane(&read_csv(&arts_p).unwrap_or_else(|_| fail("artifacts")), &lane);
    let artifacts: Vec<String> = art_rows.iter().map(|r| r[1].clone()).collect();
    let dep_rows = filter_lane(&read_csv(&deps_p).unwrap_or_else(|_| fail("deps")), &lane);
    let deps: Vec<DepRow> = dep_rows
        .iter()
        .map(|r| DepRow {
            coordinate: r[1].clone(),
            provide: r[2].clone(),
            version: r[3].clone(),
            source_url: r[4].clone(),
            source_hash: r[5].clone(),
            patch_url: r[6].clone(),
        })
        .collect();
    let (_, mir_rows) = read_csv(&mirrors_p).unwrap_or_else(|_| fail("mirrors"));
    let mirrors: HashSet<String> = mir_rows.into_iter().map(|r| r[0].clone()).collect();
    let (_, pin_rows) = read_csv(&pins_p).unwrap_or_else(|_| fail("pins"));
    let pins: Vec<PinRow> = pin_rows
        .into_iter()
        .map(|r| PinRow {
            dep: r[0].clone(),
            version: r[1].clone(),
            sha256: r[2].clone(),
        })
        .collect();
    let xor_rows_f = filter_lane(&read_csv(&xor_p).unwrap_or_else(|_| fail("xor")), &lane);
    let xor_rows: Vec<(String, String)> = xor_rows_f
        .iter()
        .map(|r| (r[1].clone(), r[2].clone()))
        .collect();
    let (_, ban_rows) = read_csv(&bans_p).unwrap_or_else(|_| fail("bans"));
    let bans: HashSet<String> = ban_rows.into_iter().map(|r| r[0].clone()).collect();
    let (_, forb_rows) = read_csv(&forb_p).unwrap_or_else(|_| fail("forbidden-hosts"));
    let forbidden: Vec<String> = forb_rows.into_iter().map(|r| r[0].clone()).collect();
    let (_, cap_rows) = read_csv(&caps_p).unwrap_or_else(|_| fail("version-caps"));
    let version_caps: HashMap<String, String> =
        cap_rows.into_iter().map(|r| (r[0].clone(), r[1].clone())).collect();

    let parsed_risks = read_csv(&risk_p).unwrap_or_else(|_| fail("risk-policy"));
    if parsed_risks.0 != ["kind", "risk"] {
        fail("risk-policy: bad header");
    }
    let required_risks = [
        "remote",
        "hashdrift",
        "versiondrift",
        "mirrormiss",
        "provcollide",
        "xor",
        "missingpin",
        "ban",
        "cap",
    ];
    let mut risks: HashMap<String, u32> = HashMap::new();
    for row in &parsed_risks.1 {
        if row.len() < 2 {
            fail("risk-policy: malformed row");
        }
        let score: u32 = row[1].parse().unwrap_or_else(|_| fail("risk-policy: bad risk"));
        if score == 0 {
            fail("risk-policy: risk must be positive");
        }
        if risks.insert(row[0].clone(), score).is_some() {
            fail("risk-policy: duplicate kind");
        }
    }
    for kind in required_risks {
        if !risks.contains_key(kind) {
            fail("risk-policy: missing kind");
        }
    }

    let required = ["ban", "remote", "xor", "provcollide", "cap"];
    let parsed_policy =
        read_csv(&cascade_policy_p).unwrap_or_else(|_| fail("cascade-policy"));
    if parsed_policy.0 != ["lane", "prefix", "decay", "max_hops"] {
        fail("cascade-policy: bad header");
    }
    let mut cascade_policy: HashMap<String, CascadePolicy> = HashMap::new();
    for row in filter_lane(&parsed_policy, &lane) {
        if row.len() < 4 || !required.contains(&row[1].as_str()) {
            fail("cascade-policy: invalid row");
        }
        let decay: u32 = row[2].parse().unwrap_or_else(|_| fail("cascade-policy: decay"));
        if decay == 0 {
            fail("cascade-policy: zero decay");
        }
        let max_hops: u32 = row[3].parse().unwrap_or_else(|_| fail("cascade-policy: hops"));
        if cascade_policy
            .insert(row[1].clone(), CascadePolicy { decay, max_hops })
            .is_some()
        {
            fail("cascade-policy: duplicate");
        }
    }
    for prefix in required {
        if !cascade_policy.contains_key(prefix) {
            fail("cascade-policy: missing prefix");
        }
    }

    let parsed_blocks =
        read_csv(&cascade_route_blocks_p).unwrap_or_else(|_| fail("cascade-route-blocks"));
    if parsed_blocks.0 != ["lane", "prefix", "block_match"] {
        fail("cascade-route-blocks: bad header");
    }
    let mut cascade_route_blocks: HashMap<String, Vec<String>> = HashMap::new();
    let mut seen = HashSet::new();
    for row in filter_lane(&parsed_blocks, &lane) {
        if row.len() < 3 || !required.contains(&row[1].as_str()) || row[2].is_empty() {
            fail("cascade-route-blocks: invalid row");
        }
        if !seen.insert((row[1].clone(), row[2].clone())) {
            fail("cascade-route-blocks: duplicate");
        }
        cascade_route_blocks
            .entry(row[1].clone())
            .or_default()
            .push(row[2].clone());
    }

    let report = inspect(
        &lane,
        hops,
        &edges,
        &artifacts,
        &deps,
        &mirrors,
        &pins,
        &xor_rows,
        &bans,
        &forbidden,
        &version_caps,
        &risks,
        &cascade_policy,
        &cascade_route_blocks,
    );
    std::fs::write(&out, report_to_json(&report) + "\n").unwrap_or_else(|_| fail("write"));
}

fn filter_lane(parsed: &(Vec<String>, Vec<Vec<String>>), lane: &str) -> Vec<Vec<String>> {
    parsed
        .1
        .iter()
        .filter(|r| r.first().map(|c| c.as_str()) == Some(lane))
        .cloned()
        .collect()
}


use pixilock_graph::cascade_routes_blocked;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::path::Path;

pub use pixilock_graph::Edge;

#[derive(Clone, Debug)]
pub struct DepRow {
    pub coordinate: String,
    pub provide: String,
    pub version: String,
    pub source_url: String,
    pub source_hash: String,
    pub patch_url: String,
}

#[derive(Clone, Debug)]
pub struct PinRow {
    pub dep: String,
    pub version: String,
    pub sha256: String,
}

#[derive(Clone, Debug)]
pub struct CascadePolicy {
    pub decay: u32,
    pub max_hops: u32,
}

#[derive(Clone, Debug)]
pub struct ArtifactReport {
    pub coordinate: String,
    pub status: String,
    pub holds: Vec<String>,
    pub risk_score: u32,
}

#[derive(Clone, Debug)]
pub struct InspectReport {
    pub lane: String,
    pub retention_hops: u32,
    pub artifacts: Vec<ArtifactReport>,
    pub totals: BTreeMap<String, u32>,
}

fn strip_sha(s: &str) -> String {
    let t = s.trim();
    if let Some(rest) = t.strip_prefix("sha256:") {
        rest.to_string()
    } else {
        t.to_string()
    }
}

fn parse_ver(v: &str) -> (u32, u32, u32) {
    let mut it = v.split('.');
    let a = it.next().unwrap_or("0").parse().unwrap_or(0);
    let b = it.next().unwrap_or("0").parse().unwrap_or(0);
    let c = it.next().unwrap_or("0").parse().unwrap_or(0);
    (a, b, c)
}

fn ver_gt(a: &str, b: &str) -> bool {
    parse_ver(a) > parse_ver(b)
}

fn basename_of(url: &str) -> String {
    Path::new(url.trim_end_matches('/'))
        .file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default()
}

fn risk_of(risks: &HashMap<String, u32>, kind: &str) -> u32 {
    *risks.get(kind).unwrap_or(&1)
}

pub fn inspect(
    lane: &str,
    retention_hops: u32,
    edges: &[Edge],
    artifacts: &[String],
    deps: &[DepRow],
    mirrors: &HashSet<String>,
    pins: &[PinRow],
    xor_rows: &[(String, String)],
    bans: &HashSet<String>,
    forbidden_hosts: &[String],
    version_caps: &HashMap<String, String>,
    risks: &HashMap<String, u32>,
    cascade_policy: &HashMap<String, CascadePolicy>,
    cascade_route_blocks: &HashMap<String, Vec<String>>,
) -> InspectReport {
    let art_set: HashSet<String> = artifacts.iter().cloned().collect();
    let mut risk: BTreeMap<String, BTreeMap<String, u32>> = BTreeMap::new();
    for a in artifacts {
        risk.insert(a.clone(), BTreeMap::new());
    }
    let pin_map: HashMap<String, PinRow> = pins
        .iter()
        .map(|p| (format!("dep:{}", p.dep), p.clone()))
        .collect();

    {
        let mut add = |coord: &str, hold: String, r: u32| {
            if let Some(m) = risk.get_mut(coord) {
                let e = m.entry(hold).or_insert(0);
                *e = (*e).max(r);
            }
        };

        for w in deps {
            if !art_set.contains(&w.coordinate) {
                continue;
            }
            let src = w.source_url.as_str();
            let remote_src =
                !src.starts_with("file:///") || forbidden_hosts.iter().any(|h| src.contains(h));
            if remote_src {
                add(
                    &w.coordinate,
                    format!("remote:{}:source", w.coordinate),
                    risk_of(risks, "remote"),
                );
            }
            if !w.patch_url.is_empty() {
                let p = w.patch_url.as_str();
                let remote_p =
                    !p.starts_with("file:///") || forbidden_hosts.iter().any(|h| p.contains(h));
                if remote_p {
                    add(
                        &w.coordinate,
                        format!("remote:{}:patch", w.coordinate),
                        risk_of(risks, "remote"),
                    );
                }
            }
            if let Some(pin) = pin_map.get(&w.coordinate) {
                let exp = strip_sha(&pin.sha256);
                let act = strip_sha(&w.source_hash);
                if exp != act {
                    add(
                        &w.coordinate,
                        format!("hashdrift:{}:{}:{}", w.coordinate, exp, act),
                        risk_of(risks, "hashdrift"),
                    );
                }
                if pin.version != w.version {
                    add(
                        &w.coordinate,
                        format!(
                            "versiondrift:{}:{}:{}",
                            w.coordinate, pin.version, w.version
                        ),
                        risk_of(risks, "versiondrift"),
                    );
                }
            } else {
                add(
                    &w.coordinate,
                    format!("missingpin:{}", w.coordinate),
                    risk_of(risks, "missingpin"),
                );
            }
            let base = basename_of(src);
            if !base.is_empty() && !mirrors.contains(&base) {
                add(
                    &w.coordinate,
                    format!("mirrormiss:{}:{}", w.coordinate, base),
                    risk_of(risks, "mirrormiss"),
                );
            }
        }

        let mut by_provide: HashMap<String, BTreeSet<String>> = HashMap::new();
        for w in deps {
            if art_set.contains(&w.coordinate) {
                by_provide
                    .entry(w.provide.clone())
                    .or_default()
                    .insert(w.coordinate.clone());
            }
        }
        for (provide, set) in by_provide {
            if set.len() < 2 {
                continue;
            }
            let joined = set.iter().cloned().collect::<Vec<_>>().join("|");
            let hold = format!("provcollide:{}:{}", provide, joined);
            for c in &set {
                add(c, hold.clone(), risk_of(risks, "provcollide"));
            }
        }

        let mut provide_to_deps: HashMap<String, BTreeSet<String>> = HashMap::new();
        for w in deps {
            if art_set.contains(&w.coordinate) {
                provide_to_deps
                    .entry(w.provide.clone())
                    .or_default()
                    .insert(w.coordinate.clone());
            }
        }
        let mut by_group: HashMap<String, BTreeSet<String>> = HashMap::new();
        for (group, provide) in xor_rows {
            if provide_to_deps.contains_key(provide) {
                by_group
                    .entry(group.clone())
                    .or_default()
                    .insert(provide.clone());
            }
        }
        for (group, provides) in by_group {
            if provides.len() < 2 {
                continue;
            }
            let joined = provides.iter().cloned().collect::<Vec<_>>().join("|");
            let hold = format!("xor:{}:{}", group, joined);
            for p in &provides {
                if let Some(coords) = provide_to_deps.get(p) {
                    for coord in coords {
                        add(coord, hold.clone(), risk_of(risks, "xor"));
                    }
                }
            }
        }

        for a in artifacts {
            if bans.contains(a) {
                add(a, format!("ban:{}", a), risk_of(risks, "ban"));
            }
        }

        for w in deps {
            if !art_set.contains(&w.coordinate) {
                continue;
            }
            if let Some(maxv) = version_caps.get(&w.coordinate) {
                if ver_gt(&w.version, maxv) {
                    add(
                        &w.coordinate,
                        format!("cap:{}:{}:{}", w.coordinate, w.version, maxv),
                        risk_of(risks, "cap"),
                    );
                }
            }
        }
    }

    let mut origin_holds: HashMap<String, Vec<(String, u32)>> = HashMap::new();
    for (coord, map) in &risk {
        for (h, r) in map {
            if h.starts_with("ban:")
                || h.starts_with("remote:")
                || h.starts_with("xor:")
                || h.starts_with("provcollide:")
                || h.starts_with("cap:")
            {
                origin_holds
                    .entry(coord.clone())
                    .or_default()
                    .push((h.clone(), *r));
            }
        }
    }
    for (prefix, policy) in cascade_policy {
        let origins: HashSet<String> = origin_holds
            .iter()
            .filter(|(_, holds)| {
                holds
                    .iter()
                    .any(|(hold, _)| hold.split(':').next() == Some(prefix.as_str()))
            })
            .map(|(origin, _)| origin.clone())
            .collect();
        let route_hops = retention_hops.min(policy.max_hops);
        let empty = Vec::new();
        let blocked = cascade_route_blocks.get(prefix).unwrap_or(&empty);
        let cascades = cascade_routes_blocked(edges, &origins, route_hops, blocked);
        for (dep, origin_routes) in cascades {
            for (origin, route) in origin_routes {
                if let Some(hs) = origin_holds.get(&origin) {
                    for (h, r) in hs
                        .iter()
                        .filter(|(hold, _)| hold.split(':').next() == Some(prefix.as_str()))
                    {
                        let attenuated = (*r)
                            .saturating_sub(policy.decay.saturating_mul(route.dist))
                            .max(1);
                        if let Some(m) = risk.get_mut(&dep) {
                            let hold = format!(
                                "cascade:{}:{}@{}:{}",
                                route.dist, origin, route.via, h
                            );
                            let e = m.entry(hold).or_insert(0);
                            *e = (*e).max(attenuated);
                        }
                    }
                }
            }
        }
    }

    let mut totals: BTreeMap<String, u32> = [
        "release",
        "hold",
        "remotes",
        "hashdrifts",
        "versiondrifts",
        "mirrormisses",
        "provcollides",
        "xors",
        "missingpins",
        "bans",
        "caps",
        "cascades",
        "risk_score_total",
    ]
    .into_iter()
    .map(|k| (k.to_string(), 0u32))
    .collect();

    let mut reports = Vec::new();
    for coord in artifacts.iter().cloned().collect::<BTreeSet<_>>() {
        let map = risk.get(&coord).cloned().unwrap_or_default();
        let holds: Vec<String> = map.keys().cloned().collect();
        let score: u32 = map.values().sum();
        for h in &holds {
            if h.starts_with("remote:") {
                *totals.get_mut("remotes").unwrap() += 1;
            } else if h.starts_with("hashdrift:") {
                *totals.get_mut("hashdrifts").unwrap() += 1;
            } else if h.starts_with("versiondrift:") {
                *totals.get_mut("versiondrifts").unwrap() += 1;
            } else if h.starts_with("mirrormiss:") {
                *totals.get_mut("mirrormisses").unwrap() += 1;
            } else if h.starts_with("provcollide:") {
                *totals.get_mut("provcollides").unwrap() += 1;
            } else if h.starts_with("xor:") {
                *totals.get_mut("xors").unwrap() += 1;
            } else if h.starts_with("missingpin:") {
                *totals.get_mut("missingpins").unwrap() += 1;
            } else if h.starts_with("ban:") {
                *totals.get_mut("bans").unwrap() += 1;
            } else if h.starts_with("cap:") {
                *totals.get_mut("caps").unwrap() += 1;
            } else if h.starts_with("cascade:") {
                *totals.get_mut("cascades").unwrap() += 1;
            }
        }
        let status = if holds.is_empty() {
            *totals.get_mut("release").unwrap() += 1;
            "release"
        } else {
            *totals.get_mut("hold").unwrap() += 1;
            "hold"
        };
        *totals.get_mut("risk_score_total").unwrap() += score;
        reports.push(ArtifactReport {
            coordinate: coord,
            status: status.into(),
            holds,
            risk_score: score,
        });
    }
    InspectReport {
        lane: lane.into(),
        retention_hops,
        artifacts: reports,
        totals,
    }
}

pub fn report_to_json(r: &InspectReport) -> String {
    let mut arts = String::from("[");
    for (i, a) in r.artifacts.iter().enumerate() {
        if i > 0 {
            arts.push(',');
        }
        let holds = a
            .holds
            .iter()
            .map(|h| format!("\"{}\"", esc(h)))
            .collect::<Vec<_>>()
            .join(",");
        arts.push_str(&format!(
            "{{\"coordinate\":\"{}\",\"status\":\"{}\",\"holds\":[{}],\"risk_score\":{}}}",
            esc(&a.coordinate),
            esc(&a.status),
            holds,
            a.risk_score
        ));
    }
    arts.push(']');
    let mut totals = String::from("{");
    for (i, (k, v)) in r.totals.iter().enumerate() {
        if i > 0 {
            totals.push(',');
        }
        totals.push_str(&format!("\"{}\":{}", esc(k), v));
    }
    totals.push('}');
    format!(
        "{{\"lane\":\"{}\",\"retention_hops\":{},\"artifacts\":{},\"totals\":{}}}",
        esc(&r.lane),
        r.retention_hops,
        arts,
        totals
    )
}
fn esc(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

pub fn read_csv(path: &str) -> Result<(Vec<String>, Vec<Vec<String>>), String> {
    let text = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut lines = text.lines().filter(|l| !l.trim().is_empty());
    let header = lines
        .next()
        .ok_or_else(|| "missing header".to_string())?
        .split(',')
        .map(|s| s.trim().to_string())
        .collect::<Vec<_>>();
    let rows = lines
        .map(|l| l.split(',').map(|s| s.trim().to_string()).collect())
        .collect();
    Ok((header, rows))
}

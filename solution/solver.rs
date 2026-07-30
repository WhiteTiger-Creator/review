// Oracle solution: recover the hidden retention policy by probing the sealed
// daemon, then decide every request in the audit set.
//
// This does NOT embed the policy. It performs the same black-box discovery an
// agent must do: it derives the domain (services, sizes, ages, disk levels)
// from the audit request set, screens every service against a reference at two
// probe points to find which ones behave differently, characterizes the
// reference service's full decision surface, characterizes any divergent
// service directly, and only then decides every request. Nothing here assumes
// which services are special or what the thresholds are; those are discovered
// from observed decisions, never hardcoded.
//
// Written in std-only Rust: no external crates are vendored into this
// environment (matching the same "no external dependency risk" principle
// that motivated using Go's stdlib json elsewhere in this portfolio), so this
// includes a small hand-rolled JSON reader/writer sufficient for the flat
// object shapes this task actually uses. It does not attempt to be a general
// JSON library.

use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Write;
use std::process::{Command, Stdio};

const DECIDE_PATH: &str = "/opt/retention/decide";

// ---------------------------------------------------------------------------
// Minimal JSON: just enough to parse/emit flat objects and arrays of them.
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
enum Json {
    Str(String),
    Num(i64),
    Arr(Vec<Json>),
    Obj(Vec<(String, Json)>),
}

impl Json {
    fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Obj(fields) => fields.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }
    fn as_str(&self) -> &str {
        match self {
            Json::Str(s) => s,
            _ => panic!("expected string, got {:?}", self),
        }
    }
    fn as_i64(&self) -> i64 {
        match self {
            Json::Num(n) => *n,
            _ => panic!("expected number, got {:?}", self),
        }
    }
    fn as_arr(&self) -> &Vec<Json> {
        match self {
            Json::Arr(a) => a,
            _ => panic!("expected array, got {:?}", self),
        }
    }

    fn write(&self, out: &mut String) {
        match self {
            Json::Str(s) => {
                out.push('"');
                for c in s.chars() {
                    match c {
                        '"' => out.push_str("\\\""),
                        '\\' => out.push_str("\\\\"),
                        '\n' => out.push_str("\\n"),
                        _ => out.push(c),
                    }
                }
                out.push('"');
            }
            Json::Num(n) => out.push_str(&n.to_string()),
            Json::Arr(items) => {
                out.push('[');
                for (i, item) in items.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    item.write(out);
                }
                out.push(']');
            }
            Json::Obj(fields) => {
                out.push('{');
                for (i, (k, v)) in fields.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    Json::Str(k.clone()).write(out);
                    out.push(':');
                    v.write(out);
                }
                out.push('}');
            }
        }
    }
    fn to_string(&self) -> String {
        let mut s = String::new();
        self.write(&mut s);
        s
    }
}

struct Parser<'a> {
    b: &'a [u8],
    i: usize,
}
impl<'a> Parser<'a> {
    fn new(s: &'a str) -> Self {
        Parser { b: s.as_bytes(), i: 0 }
    }
    fn skip_ws(&mut self) {
        while self.i < self.b.len() && (self.b[self.i] as char).is_whitespace() {
            self.i += 1;
        }
    }
    fn peek(&self) -> u8 {
        self.b[self.i]
    }
    fn expect(&mut self, c: u8) {
        assert_eq!(self.b[self.i], c, "expected {:?} at {}", c as char, self.i);
        self.i += 1;
    }
    fn parse_value(&mut self) -> Json {
        self.skip_ws();
        match self.peek() {
            b'"' => self.parse_string(),
            b'[' => self.parse_array(),
            b'{' => self.parse_object(),
            b't' => {
                self.i += 4;
                Json::Num(1)
            }
            b'f' => {
                self.i += 5;
                Json::Num(0)
            }
            _ => self.parse_number(),
        }
    }
    fn parse_string(&mut self) -> Json {
        self.expect(b'"');
        let mut s = String::new();
        loop {
            let c = self.b[self.i];
            self.i += 1;
            match c {
                b'"' => break,
                b'\\' => {
                    let esc = self.b[self.i];
                    self.i += 1;
                    match esc {
                        b'n' => s.push('\n'),
                        b't' => s.push('\t'),
                        b'"' => s.push('"'),
                        b'\\' => s.push('\\'),
                        b'/' => s.push('/'),
                        other => s.push(other as char),
                    }
                }
                _ => s.push(c as char),
            }
        }
        Json::Str(s)
    }
    fn parse_number(&mut self) -> Json {
        let start = self.i;
        if self.peek() == b'-' {
            self.i += 1;
        }
        while self.i < self.b.len() {
            let c = self.b[self.i];
            if c.is_ascii_digit() {
                self.i += 1;
            } else {
                break;
            }
        }
        let s = std::str::from_utf8(&self.b[start..self.i]).unwrap();
        Json::Num(s.parse().unwrap())
    }
    fn parse_array(&mut self) -> Json {
        self.expect(b'[');
        let mut items = Vec::new();
        self.skip_ws();
        if self.peek() == b']' {
            self.i += 1;
            return Json::Arr(items);
        }
        loop {
            items.push(self.parse_value());
            self.skip_ws();
            match self.peek() {
                b',' => {
                    self.i += 1;
                }
                b']' => {
                    self.i += 1;
                    break;
                }
                _ => panic!("bad array at {}", self.i),
            }
        }
        Json::Arr(items)
    }
    fn parse_object(&mut self) -> Json {
        self.expect(b'{');
        let mut fields = Vec::new();
        self.skip_ws();
        if self.peek() == b'}' {
            self.i += 1;
            return Json::Obj(fields);
        }
        loop {
            self.skip_ws();
            let key = self.parse_string();
            self.skip_ws();
            self.expect(b':');
            let val = self.parse_value();
            fields.push((key.as_str().to_string(), val));
            self.skip_ws();
            match self.peek() {
                b',' => {
                    self.i += 1;
                }
                b'}' => {
                    self.i += 1;
                    break;
                }
                _ => panic!("bad object at {}", self.i),
            }
        }
        Json::Obj(fields)
    }
}

fn parse_json(s: &str) -> Json {
    Parser::new(s).parse_value()
}

// ---------------------------------------------------------------------------
// Probing
// ---------------------------------------------------------------------------

struct Prober {
    probes: u32,
    cache: HashMap<(String, i64, i64, i64), String>,
    exhausted: bool,
}

impl Prober {
    fn new() -> Self {
        Prober { probes: 0, cache: HashMap::new(), exhausted: false }
    }

    // ask queries the sealed daemon for one decision, memoized so repeated
    // queries never spend budget twice.
    fn ask(&mut self, service: &str, size: i64, age: i64, disk: i64) -> String {
        if self.exhausted {
            return String::new();
        }
        let key = (service.to_string(), size, age, disk);
        if let Some(v) = self.cache.get(&key) {
            return v.clone();
        }
        let body = Json::Obj(vec![
            ("service".to_string(), Json::Str(service.to_string())),
            ("size_mb".to_string(), Json::Num(size)),
            ("age_days".to_string(), Json::Num(age)),
            ("disk_pct".to_string(), Json::Num(disk)),
        ])
        .to_string();

        let mut child = Command::new(DECIDE_PATH)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .expect("failed to spawn decide");
        child.stdin.take().unwrap().write_all(body.as_bytes()).ok();
        let output = child.wait_with_output().expect("failed to wait on decide");
        self.probes += 1;
        let text = String::from_utf8_lossy(&output.stdout).trim().to_string();

        if text.contains("LIMIT") {
            self.exhausted = true;
            eprintln!("warning: query budget exhausted after {} probes", self.probes);
            return String::new();
        }
        let parsed = parse_json(&text);
        let decision = match parsed.get("decision") {
            Some(Json::Str(s)) if !s.is_empty() => s.clone(),
            _ => {
                self.exhausted = true;
                eprintln!("warning: unparsable reply {:?}, stopping probes", text);
                return String::new();
            }
        };
        self.cache.insert(key, decision.clone());
        decision
    }
}

fn majority(votes: &HashMap<String, String>) -> String {
    let mut counts: HashMap<&String, i32> = HashMap::new();
    for v in votes.values() {
        *counts.entry(v).or_insert(0) += 1;
    }
    counts
        .into_iter()
        .max_by_key(|(_, n)| *n)
        .map(|(v, _)| v.clone())
        .unwrap_or_default()
}

fn sorted_unique_i64(vals: HashSet<i64>) -> Vec<i64> {
    let mut v: Vec<i64> = vals.into_iter().collect();
    v.sort();
    v
}

fn main() {
    let raw = fs::read_to_string("/app/challenge/requests.json").expect("read requests.json");
    let root = parse_json(&raw);
    let requests = root.get("requests").expect("no requests field").as_arr().clone();

    // Derive the domain from the audit set rather than assuming it.
    let mut svc_set: HashSet<String> = HashSet::new();
    let mut size_set: HashSet<i64> = HashSet::new();
    let mut age_set: HashSet<i64> = HashSet::new();
    let mut disk_set: HashSet<i64> = HashSet::new();
    for r in &requests {
        svc_set.insert(r.get("service").unwrap().as_str().to_string());
        size_set.insert(r.get("size_mb").unwrap().as_i64());
        age_set.insert(r.get("age_days").unwrap().as_i64());
        disk_set.insert(r.get("disk_pct").unwrap().as_i64());
    }
    let mut services: Vec<String> = svc_set.into_iter().collect();
    services.sort();
    let sizes = sorted_unique_i64(size_set);
    let ages = sorted_unique_i64(age_set);
    let disks = sorted_unique_i64(disk_set);
    if services.is_empty() || sizes.is_empty() || ages.is_empty() || disks.is_empty() {
        panic!("empty domain derived from requests.json");
    }
    let (low_disk, critical_disk) = (disks[0], disks[disks.len() - 1]);
    let (min_size, max_size) = (sizes[0], sizes[sizes.len() - 1]);
    let min_age = ages[0];

    let mut p = Prober::new();

    // Screen A: sweep every size domain value per service, at low disk and the
    // youngest age (so only the size threshold drives the decision). A single
    // probe point cannot safely screen for a size-threshold difference, because
    // the probed size might land on the same side of every service's threshold
    // regardless of where each threshold actually sits; sweeping every domain
    // value is the only way to be sure a divergence is not missed. This also
    // doubles as one full row (age = min_age) of each service's base grid, so
    // it is not wasted probing.
    let mut size_row: HashMap<String, HashMap<i64, String>> = HashMap::new();
    for s in &services {
        let mut row = HashMap::new();
        for &sz in &sizes {
            row.insert(sz, p.ask(s, sz, min_age, low_disk));
        }
        size_row.insert(s.clone(), row);
    }
    let mut size_special: HashSet<String> = HashSet::new();
    for &sz in &sizes {
        let mut votes: HashMap<String, String> = HashMap::new();
        for s in &services {
            votes.insert(s.clone(), size_row[s][&sz].clone());
        }
        let maj = majority(&votes);
        for s in &services {
            if size_row[s][&sz] != maj {
                size_special.insert(s.clone());
            }
        }
    }

    // Screen B: does this service's decision differ from the majority under
    // critical disk pressure, at a size/age combo whose base decision would
    // otherwise be the mildest possible?
    let mut screen_b: HashMap<String, String> = HashMap::new();
    for s in &services {
        screen_b.insert(s.clone(), p.ask(s, min_size, min_age, critical_disk));
    }
    let majority_b = majority(&screen_b);
    let mut pressure_special: HashSet<String> = HashSet::new();
    for s in &services {
        if screen_b[s] != majority_b {
            pressure_special.insert(s.clone());
        }
    }

    // Pick a reference service that is ordinary on both axes, to characterize
    // the shared model once instead of once per service.
    let mut reference = services[0].clone();
    for s in &services {
        if !size_special.contains(s) && !pressure_special.contains(s) {
            reference = s.clone();
            break;
        }
    }

    // Full (size, age) base grid for the reference, at low disk (below any
    // disk effect).
    let mut ref_base: HashMap<(i64, i64), String> = HashMap::new();
    for &sz in &sizes {
        for &ag in &ages {
            ref_base.insert((sz, ag), p.ask(&reference, sz, ag, low_disk));
        }
    }

    // For every other domain disk value, classify how the reference's
    // decision surface changes there. Disk pressure is not assumed to be a
    // single all-or-nothing tier: it is checked directly, per disk value, in
    // two passes. Pass one is cheap -- every domain SIZE value (not just the
    // two extremes) at the youngest age -- because a disk value whose effect
    // is a genuine threshold shift, rather than a flat override, could be
    // confined to an interior size value that an extremes-only probe would
    // never see. If every one of those decisions agrees, and one more probe
    // at a different age also agrees, the disk value is trusted to be a
    // FLAT override (the decision is the same regardless of size or age, the
    // way a full reclaim would look). If they do not all agree, the disk
    // value has a GRADUATED effect -- the decision surface genuinely still
    // depends on size and/or age, just differently than at low disk -- and
    // pass two probes the remaining cells to characterize it exactly.
    let mut disk_grid: HashMap<i64, HashMap<(i64, i64), String>> = HashMap::new();
    disk_grid.insert(low_disk, ref_base.clone());
    let mut flat_disks: HashMap<i64, String> = HashMap::new();
    for &dk in &disks {
        if dk == low_disk {
            continue;
        }
        let mut sweep: HashMap<(i64, i64), String> = HashMap::new();
        for &sz in &sizes {
            sweep.insert((sz, min_age), p.ask(&reference, sz, min_age, dk));
        }
        let first = sweep[&(sizes[0], min_age)].clone();
        let mut is_flat = sizes.iter().all(|sz| sweep[&(*sz, min_age)] == first);
        if is_flat && ages.len() > 1 {
            let other_age = ages[ages.len() - 1];
            let confirm = p.ask(&reference, sizes[0], other_age, dk);
            is_flat = confirm == first;
        }
        if is_flat {
            flat_disks.insert(dk, first);
            disk_grid.insert(dk, sweep);
        } else {
            let mut grid = sweep;
            for &sz in &sizes {
                for &ag in &ages {
                    if ag == min_age {
                        continue;
                    }
                    grid.insert((sz, ag), p.ask(&reference, sz, ag, dk));
                }
            }
            disk_grid.insert(dk, grid);
        }
    }

    // Directly characterize any service that diverges on size: its own full
    // base grid at low disk, so its exact per-cell answers are probed rather
    // than guessed.
    let mut own_base: HashMap<String, HashMap<(i64, i64), String>> = HashMap::new();
    for s in &services {
        if !size_special.contains(s) {
            continue;
        }
        let mut grid = HashMap::new();
        for &sz in &sizes {
            for &ag in &ages {
                grid.insert((sz, ag), p.ask(s, sz, ag, low_disk));
            }
        }
        own_base.insert(s.clone(), grid);
    }

    // For a size-divergent service, do not assume its own threshold behaves
    // the same way under a graduated disk value as the reference's does: a
    // couple of spot-check probes per graduated disk confirm whether this
    // service's decision there matches its own low-disk grid. Only if they
    // disagree is the full grid re-probed for that disk value.
    let mut own_disk_grid: HashMap<String, HashMap<i64, HashMap<(i64, i64), String>>> = HashMap::new();
    for s in &services {
        if !size_special.contains(s) {
            continue;
        }
        let mut per_disk: HashMap<i64, HashMap<(i64, i64), String>> = HashMap::new();
        per_disk.insert(low_disk, own_base[s].clone());
        for &dk in &disks {
            if dk == low_disk || flat_disks.contains_key(&dk) {
                continue;
            }
            let spot: [(i64, i64); 2] = [(sizes[0], ages[0]), (sizes[sizes.len() - 1], ages[ages.len() - 1])];
            let mut matches = true;
            for &(sz, ag) in &spot {
                let got = p.ask(s, sz, ag, dk);
                let want = own_base[s].get(&(sz, ag)).cloned().unwrap_or_default();
                if !got.is_empty() && got != want {
                    matches = false;
                }
            }
            if matches {
                per_disk.insert(dk, own_base[s].clone());
            } else {
                let mut grid = HashMap::new();
                for &sz in &sizes {
                    for &ag in &ages {
                        grid.insert((sz, ag), p.ask(s, sz, ag, dk));
                    }
                }
                per_disk.insert(dk, grid);
            }
        }
        own_disk_grid.insert(s.clone(), per_disk);
    }

    // Directly characterize any service that diverges under FLAT disk
    // pressure specifically: what it decides at each flat disk, sampled at
    // more than one base state to confirm the decision does not depend on
    // which state it started from. A pressure-divergent service is NOT
    // assumed to also diverge at a graduated disk value -- it falls back to
    // the reference's (or its own, if also size-special) graduated grid
    // there, and that assumption is exactly what the pytest checks verify.
    let base_states: [(i64, i64); 2] = [(min_size, min_age), (max_size, min_age)];
    let mut own_flat: HashMap<String, HashMap<i64, String>> = HashMap::new();
    for s in &services {
        if !pressure_special.contains(s) {
            continue;
        }
        let mut per_disk: HashMap<i64, String> = HashMap::new();
        for &pd in flat_disks.keys() {
            let mut last = String::new();
            for &(bs0, bs1) in &base_states {
                let d = p.ask(s, bs0, bs1, pd);
                if !d.is_empty() {
                    last = d;
                }
            }
            per_disk.insert(pd, last);
        }
        own_flat.insert(s.clone(), per_disk);
    }
    let flat_fallback = majority(&screen_b); // the ordinary flat-disk decision

    // Spot-check a few services that screened as fully ordinary, to raise
    // confidence they really share the reference's model before trusting it
    // for every one of their cells. (Kept for parity with the oracle's
    // discovery process; not consulted by decide() below, matching the Go
    // solver.)
    for s in &services {
        if size_special.contains(s) || pressure_special.contains(s) || *s == reference || p.exhausted {
            continue;
        }
        for i in 0..2.min(sizes.len()) {
            let sz = sizes[i];
            let ag = ages[i % ages.len()];
            p.ask(s, sz, ag, low_disk);
        }
    }

    let decide = |service: &str, sz: i64, ag: i64, dk: i64| -> String {
        if flat_disks.contains_key(&dk) {
            if let Some(per_disk) = own_flat.get(service) {
                if let Some(d) = per_disk.get(&dk) {
                    return d.clone();
                }
            }
            if let Some(per_disk) = own_disk_grid.get(service) {
                if let Some(grid) = per_disk.get(&dk) {
                    if let Some(d) = grid.get(&(sz, ag)) {
                        return d.clone();
                    }
                }
            }
            return flat_disks.get(&dk).cloned().unwrap_or(flat_fallback.clone());
        }
        if let Some(per_disk) = own_disk_grid.get(service) {
            if let Some(grid) = per_disk.get(&dk).or_else(|| per_disk.get(&low_disk)) {
                if let Some(d) = grid.get(&(sz, ag)) {
                    return d.clone();
                }
            }
        }
        if let Some(grid) = disk_grid.get(&dk).or_else(|| disk_grid.get(&low_disk)) {
            if let Some(d) = grid.get(&(sz, ag)) {
                return d.clone();
            }
        }
        "KEEP".to_string() // never actually reached once probing succeeds
    };

    let mut decisions: Vec<(i64, String)> = Vec::new();
    for r in &requests {
        let id = r.get("id").unwrap().as_i64();
        let service = r.get("service").unwrap().as_str();
        let sz = r.get("size_mb").unwrap().as_i64();
        let ag = r.get("age_days").unwrap().as_i64();
        let dk = r.get("disk_pct").unwrap().as_i64();
        decisions.push((id, decide(service, sz, ag, dk)));
    }

    // Spot-check a handful of computed cells against the live daemon before
    // submitting, catching a wrong generalization while there is still budget
    // left to notice it.
    let mut checked = 0;
    for r in &requests {
        if checked >= 6 || p.exhausted {
            break;
        }
        let id = r.get("id").unwrap().as_i64();
        let service = r.get("service").unwrap().as_str();
        let sz = r.get("size_mb").unwrap().as_i64();
        let ag = r.get("age_days").unwrap().as_i64();
        let dk = r.get("disk_pct").unwrap().as_i64();
        let want = decisions.iter().find(|(rid, _)| *rid == id).map(|(_, d)| d.clone()).unwrap_or_default();
        let got = p.ask(service, sz, ag, dk);
        if !got.is_empty() && got != want {
            panic!(
                "generalisation wrong for id {} ({} size={} age={} disk={}): got {} want {}",
                id, service, sz, ag, dk, got, want
            );
        }
        checked += 1;
    }

    fs::create_dir_all("/app/out").expect("mkdir /app/out");
    let out_json = Json::Obj(vec![(
        "decisions".to_string(),
        Json::Arr(
            decisions
                .iter()
                .map(|(id, d)| {
                    Json::Obj(vec![
                        ("id".to_string(), Json::Num(*id)),
                        ("decision".to_string(), Json::Str(d.clone())),
                    ])
                })
                .collect(),
        ),
    )]);
    fs::write("/app/out/decisions.json", out_json.to_string()).expect("write decisions.json");
    eprintln!("recovered policy using {} probes; wrote {} decisions", p.probes, decisions.len());
}

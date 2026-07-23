use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use m7q::{op_a, Ctx, Row};
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
struct SiteRows {
    site_id: String,
    eta: f64,
    rows: Vec<RowData>,
}

#[derive(Serialize, Deserialize, Clone)]
struct RowData {
    arm: u32,
    weight_tok: u32,
    mode: Vec<u8>,
}

impl From<Row> for RowData {
    fn from(r: Row) -> Self {
        Self {
            arm: r.arm,
            weight_tok: r.weight_tok,
            mode: r.mode,
        }
    }
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

fn read_sched_eta(path: &Path) -> f64 {
    let txt = fs::read_to_string(path).unwrap_or_default();
    for (i, line) in txt.lines().enumerate() {
        if i == 0 {
            continue;
        }
        let p: Vec<&str> = line.split('\t').collect();
        if p.len() >= 3 {
            return p[2].parse().unwrap_or(0.15);
        }
    }
    0.15
}

fn main() {
    let mut site_root = PathBuf::from("/app/environment/k8");
    let mut out = PathBuf::from("/tmp/wf_stage_a/rows.json");
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--site-root" => site_root = PathBuf::from(args.next().expect("site-root")),
            "--out" => out = PathBuf::from(args.next().expect("out")),
            _ => {}
        }
    }
    let mut all = Vec::new();
    for site in ["s01", "s02", "s03"] {
        let eta = read_sched_eta(&site_root.join(site).join("schedule.tsv"));
        let buf = fs::read(site_root.join(site).join("xslice.bin")).expect("xslice");
        let ctx = Ctx { eta };
        let rows: Vec<RowData> = op_a(&buf, &ctx).into_iter().map(RowData::from).collect();
        all.push(SiteRows {
            site_id: site.to_string(),
            eta,
            rows,
        });
    }
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent).expect("mkdir");
    }
    fs::write(out, serde_json::to_string_pretty(&all).expect("json")).expect("write");
}

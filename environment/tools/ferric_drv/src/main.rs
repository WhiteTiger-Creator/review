use ferric_ws::{bind_rows, cast_bag, sift_rows, ForgeBag, GridSpec, NestEntry, NestMap, SideBag, SideRow, TraceRow};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

fn root_dir() -> PathBuf {
    if let Ok(p) = std::env::var("FERRIC_ROOT") {
        return PathBuf::from(p);
    }
    let cwd = std::env::current_dir().expect("cwd");
    if cwd.join("data/runs").is_dir() {
        return cwd;
    }
    PathBuf::from("/app/environment")
}

fn load_traces(runs: &Path) -> Vec<TraceRow> {
    let mut rows = Vec::new();
    let mut paths: Vec<PathBuf> = fs::read_dir(runs)
        .expect("runs dir")
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| {
            p.extension().and_then(|x| x.to_str()) == Some("jsonl")
                && p.file_name().and_then(|x| x.to_str()) != Some("side_bag.jsonl")
        })
        .collect();
    paths.sort();
    for p in paths {
        for line in fs::read_to_string(&p).expect("read batch").lines() {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            rows.push(serde_json::from_str(line).expect("trace row"));
        }
    }
    rows
}

fn load_side(path: &Path) -> SideBag {
    let mut rows = Vec::new();
    if path.is_file() {
        for line in fs::read_to_string(path).expect("side").lines() {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            rows.push(serde_json::from_str::<SideRow>(line).expect("side row"));
        }
    }
    SideBag { rows }
}

fn load_nest(path: &Path) -> NestMap {
    let raw: HashMap<String, NestEntry> =
        serde_json::from_str(&fs::read_to_string(path).expect("nest")).expect("nest json");
    raw
}

fn main() {
    let root = root_dir();
    let nest_path = std::env::var("FERRIC_NEST")
        .map(PathBuf::from)
        .unwrap_or_else(|_| root.join("data/nests/nest_map.json"));
    let grid_path = std::env::var("FERRIC_GRID")
        .map(PathBuf::from)
        .unwrap_or_else(|_| root.join("data/grids/grid_pub.json"));
    let bag_path = root.join("data/bags/forge_bag.json");
    let emit_dir = std::env::var("FERRIC_EMIT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/app/emit"));

    let traces = load_traces(&root.join("data/runs"));
    let side = load_side(&root.join("data/runs/side_bag.jsonl"));
    let nest = load_nest(&nest_path);
    let grid: GridSpec =
        serde_json::from_str(&fs::read_to_string(&grid_path).expect("grid")).expect("grid json");
    let bag: ForgeBag =
        serde_json::from_str(&fs::read_to_string(&bag_path).expect("bag")).expect("bag json");

    let sift = sift_rows(&traces, &side);
    let bind = bind_rows(sift, &grid, &nest);
    let out = cast_bag(bind, &bag);

    fs::create_dir_all(&emit_dir).expect("emit dir");
    fs::write(
        emit_dir.join("rung_sheet.json"),
        serde_json::to_string_pretty(&out.sheet).expect("sheet"),
    )
    .expect("write sheet");
    fs::write(
        emit_dir.join("align_ledger.json"),
        serde_json::to_string_pretty(&out.ledger).expect("ledger"),
    )
    .expect("write ledger");
}

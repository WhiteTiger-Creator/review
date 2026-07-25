use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::Path;

use crate::skim_sieve::{ClassifiedFrame, FrameStatus};

#[derive(Clone)]
pub struct Frame {
    pub epoch: u16,
    pub lane: String,
    pub ts: u64,
    pub hold: bool,
    pub from_wal: bool,
}

pub struct Profile {
    pub label: String,
    pub epochs: Vec<u16>,
}

pub struct MatrixEntry {
    pub lanes: Vec<String>,
    pub mode: String,
}

pub struct Roster {
    pub backends: Vec<(String, String)>,
    pub epochs: Vec<(u16, String, u32)>,
}

pub fn load_profiles() -> HashMap<String, Profile> {
    let dir = Path::new(lattice_core::CONFIG_ROOT).join("profiles");
    let mut map = HashMap::new();
    let Ok(entries) = fs::read_dir(&dir) else {
        return map;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().map_or(true, |e| e != "toml") {
            continue;
        }
        let Ok(text) = fs::read_to_string(&path) else { continue };
        let label = extract_toml_str(&text, "label").unwrap_or_default();
        let epochs = extract_toml_array_u16(&text, "epochs");
        if !label.is_empty() {
            map.insert(label.clone(), Profile { label, epochs });
        }
    }
    map
}

pub fn load_matrix() -> HashMap<String, MatrixEntry> {
    let path = Path::new(lattice_core::OPS_ROOT).join("matrix.toml");
    let Ok(text) = fs::read_to_string(&path) else {
        return HashMap::new();
    };
    let mut map = HashMap::new();
    let mut current_section: Option<String> = None;
    let mut current_lanes: Vec<String> = Vec::new();
    let mut current_mode = String::new();

    for line in text.lines() {
        let t = line.trim();
        if t.starts_with('[') && t.ends_with(']') {
            if let Some(section) = current_section.take() {
                if !current_lanes.is_empty() {
                    map.insert(
                        section,
                        MatrixEntry {
                            lanes: current_lanes.clone(),
                            mode: current_mode.clone(),
                        },
                    );
                }
            }
            current_section = Some(t[1..t.len() - 1].to_string());
            current_lanes.clear();
            current_mode.clear();
        } else if let Some(rest) = t.strip_prefix("lanes") {
            if let Some(arr) = rest.split('=').nth(1) {
                current_lanes = parse_string_array(arr);
            }
        } else if let Some(rest) = t.strip_prefix("mode") {
            if let Some(v) = rest.split('=').nth(1) {
                current_mode = v.trim().trim_matches('"').to_string();
            }
        }
    }
    if let Some(section) = current_section {
        if !current_lanes.is_empty() {
            map.insert(
                section,
                MatrixEntry {
                    lanes: current_lanes,
                    mode: current_mode,
                },
            );
        }
    }
    map
}

pub fn load_jsonl_lane(path: &Path, lane_name: &str) -> Vec<Frame> {
    let Ok(text) = fs::read_to_string(path) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let epoch = extract_json_u16(line, "\"epoch\":").unwrap_or(0);
        let ts = extract_json_u64(line, "\"ts\":").unwrap_or(0);
        let hold = line.contains("\"hold\":true");
        out.push(Frame {
            epoch,
            lane: lane_name.to_string(),
            ts,
            hold,
            from_wal: false,
        });
    }
    out
}

pub fn evaluate(
    frames: &[ClassifiedFrame],
    profiles: &HashMap<String, Profile>,
    matrix: &HashMap<String, MatrixEntry>,
) -> Roster {
    let all_lanes = ["mqtt", "lora", "uart", "canbus", "zigbee"];
    let mut active_backends: HashSet<String> = HashSet::new();
    let mut epochs: Vec<(u16, String, u32)> = Vec::new();

    for (prof_name, profile) in profiles {
        let entry = match matrix.get(prof_name) {
            Some(e) => e,
            None => continue,
        };

        for &epoch in &profile.epochs {
            let epoch_frames: Vec<&ClassifiedFrame> = frames
                .iter()
                .filter(|f| f.epoch == epoch && entry.lanes.contains(&f.lane))
                .collect();

            let publish = match entry.mode.as_str() {
                "required-together" => entry.lanes.iter().all(|lane| {
                    epoch_frames.iter().any(|f| {
                        &f.lane == lane
                            && (f.status == FrameStatus::Active
                                || f.status == FrameStatus::Revoked)
                    })
                }),
                _ => !epoch_frames.is_empty(),
            };

            if publish {
                let count = epoch_frames
                    .iter()
                    .filter(|f| f.status != FrameStatus::Revoked && f.status != FrameStatus::Held)
                    .count() as u32;

                if count > 0 {
                    epochs.push((epoch, prof_name.clone(), count));
                }

                for f in &epoch_frames {
                    if f.status == FrameStatus::Active {
                        active_backends.insert(f.lane.clone());
                    }
                }
            }
        }
    }

    epochs.sort_by_key(|(e, _, _)| *e);

    let backends: Vec<(String, String)> = all_lanes
        .iter()
        .map(|&l| {
            let status = if active_backends.contains(l) {
                "active"
            } else {
                "inactive"
            };
            (l.to_string(), status.to_string())
        })
        .collect();

    Roster { backends, epochs }
}

fn extract_toml_str(text: &str, key: &str) -> Option<String> {
    for line in text.lines() {
        let t = line.trim();
        if let Some(rest) = t.strip_prefix(key) {
            if let Some(v) = rest.split('=').nth(1) {
                let trimmed = v.trim().trim_matches('"');
                return Some(trimmed.to_string());
            }
        }
    }
    None
}

fn extract_toml_array_u16(text: &str, key: &str) -> Vec<u16> {
    for line in text.lines() {
        let t = line.trim();
        if let Some(rest) = t.strip_prefix(key) {
            let bracket = rest.find('[').and_then(|i| rest[i + 1..].find(']').map(|j| (i, j)));
            if let Some((i, j)) = bracket {
                let inner = &rest[i + 1..i + 1 + j];
                return inner
                    .split(',')
                    .filter_map(|s| s.trim().parse::<u16>().ok())
                    .collect();
            }
        }
    }
    Vec::new()
}

fn parse_string_array(text: &str) -> Vec<String> {
    let trimmed = text.trim();
    let inner = trimmed
        .strip_prefix('[')
        .and_then(|s| s.strip_suffix(']'))
        .unwrap_or(trimmed);
    inner
        .split(',')
        .map(|s| s.trim().trim_matches('"').to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

fn extract_json_u16(line: &str, key: &str) -> Option<u16> {
    extract_json_u64(line, key).map(|v| v as u16)
}

fn extract_json_u64(line: &str, key: &str) -> Option<u64> {
    let i = line.find(key)?;
    let rest = &line[i + key.len()..];
    let digits: String = rest
        .chars()
        .skip_while(|c| !c.is_ascii_digit())
        .take_while(|c| c.is_ascii_digit())
        .collect();
    digits.parse().ok()
}

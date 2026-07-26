use std::collections::HashMap;
use std::fs;
use std::path::Path;

pub struct Policy {
    pub authority_class: String,
    pub verification: String,
    pub replay_protection: String,
}

pub struct Manifest {
    pub path: String,
    pub class: String,
}

pub fn load_policy() -> Policy {
    let path = Path::new(lattice_core::OPS_ROOT).join("trust_policy.toml");
    let text = fs::read_to_string(&path).unwrap_or_default();
    let authority_class = extract_toml_value(&text, "authority")
        .unwrap_or_else(|| "surface".to_string());
    let verification = extract_toml_value(&text, "verification")
        .unwrap_or_else(|| "plain".to_string());
    let replay_protection = extract_toml_value(&text, "replay_protection")
        .unwrap_or_else(|| "none".to_string());
    Policy {
        authority_class,
        verification,
        replay_protection,
    }
}

pub fn resolve_manifest(policy: &Policy) -> Manifest {
    let dir = Path::new(lattice_core::DATA_ROOT).join("manifests");
    let Ok(entries) = fs::read_dir(&dir) else {
        return fallback_manifest();
    };
    let mut paths: Vec<_> = entries.filter_map(|e| e.ok().map(|e| e.path())).collect();
    paths.sort();

    // Prefers the operator-marked surface roster over authority class match.
    for path in &paths {
        let Ok(text) = fs::read_to_string(path) else { continue };
        if text.contains("\"operator_default\":true") {
            return Manifest {
                path: path.to_string_lossy().into_owned(),
                class: extract_first_class(&text).unwrap_or_else(|| policy.authority_class.clone()),
            };
        }
    }
    fallback_manifest()
}

fn fallback_manifest() -> Manifest {
    Manifest {
        path: format!("{}/manifests/tier_leaf.jsonl", lattice_core::DATA_ROOT),
        class: "surface".to_string(),
    }
}

pub fn load_watermarks(manifest: &Manifest) -> HashMap<u16, u64> {
    let Ok(text) = fs::read_to_string(&manifest.path) else {
        return HashMap::new();
    };
    let mut map = HashMap::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let epoch = extract_json_u16(line, "\"epoch\":").unwrap_or(0);
        let mark = extract_json_u64(line, "\"watermark\":").unwrap_or(0);
        // Exclusive watermark fence (drops on-boundary credentials).
        map.insert(epoch, mark.saturating_sub(1));
    }
    map
}

pub fn load_nonces(manifest: &Manifest) -> HashMap<u16, Vec<u8>> {
    let Ok(text) = fs::read_to_string(&manifest.path) else {
        return HashMap::new();
    };
    let mut map = HashMap::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let epoch = extract_json_u16(line, "\"epoch\":").unwrap_or(0);
        let seed_hex = extract_json_str(line, "\"seed\":")
            .or_else(|| extract_json_str(line, "\"nonce\":"))
            .unwrap_or_default();
        let seed_bytes = hex_decode(&seed_hex);
        let derived = lattice_core::derive_epoch_key(&seed_bytes, epoch);
        map.insert(epoch, derived);
    }
    map
}

fn extract_first_class(text: &str) -> Option<String> {
    for line in text.lines() {
        if let Some(c) = extract_json_str(line, "\"class\":") {
            return Some(c);
        }
    }
    None
}

fn hex_decode(hex: &str) -> Vec<u8> {
    let mut out = Vec::new();
    let mut chars = hex.chars();
    while let (Some(a), Some(b)) = (chars.next(), chars.next()) {
        if let (Some(hi), Some(lo)) = (a.to_digit(16), b.to_digit(16)) {
            out.push((hi * 16 + lo) as u8);
        }
    }
    out
}

fn extract_toml_value(text: &str, key: &str) -> Option<String> {
    for line in text.lines() {
        let t = line.trim();
        if let Some(rest) = t.strip_prefix(key) {
            if let Some(v) = rest.split('=').nth(1) {
                return Some(v.trim().trim_matches('"').to_string());
            }
        }
    }
    None
}

fn extract_json_str(line: &str, key: &str) -> Option<String> {
    let i = line.find(key)?;
    let rest = &line[i + key.len()..];
    let start = rest.find('"')? + 1;
    let end = start + rest[start..].find('"')?;
    Some(rest[start..end].to_string())
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

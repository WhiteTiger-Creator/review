use std::collections::BTreeMap;
use std::fs;

#[derive(Clone, Debug)]
pub struct Example {
    pub label: f64,
    pub features: BTreeMap<String, f64>,
}

pub fn load(path: &str) -> Result<Vec<Example>, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut rows = Vec::new();
    for (line_no, raw) in text.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }
        let mut parts = line.split_whitespace();
        let label: f64 = parts
            .next()
            .ok_or_else(|| format!("line {} missing label", line_no + 1))?
            .parse()
            .map_err(|_| format!("line {} invalid label", line_no + 1))?;
        if label != 0.0 && label != 1.0 {
            return Err(format!("line {} label must be 0 or 1", line_no + 1));
        }
        let mut features = BTreeMap::new();
        for token in parts {
            let (name, value) = token
                .split_once(':')
                .ok_or_else(|| format!("line {} invalid feature", line_no + 1))?;
            if name.is_empty() {
                return Err(format!("line {} empty feature", line_no + 1));
            }
            let value: f64 = value
                .parse()
                .map_err(|_| format!("line {} invalid value", line_no + 1))?;
            if !value.is_finite() {
                return Err(format!("line {} non-finite value", line_no + 1));
            }
            *features.entry(name.to_string()).or_insert(0.0) += value;
        }
        rows.push(Example { label, features });
    }
    if rows.is_empty() {
        return Err("dataset is empty".to_string());
    }
    Ok(rows)
}

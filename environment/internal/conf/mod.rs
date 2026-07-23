//! Reads the lab gate file at `<root>/config/lab.toml`.

use std::path::Path;

use anyhow::{Context, Result};

/// Site holds the lab configuration read from config/lab.toml.
#[derive(Debug, Clone, Default)]
pub struct Site {
    pub site_id: String,
    pub eval_at: String,
    pub graph_generation: String,
    pub graph_lock_sha256: String,
    pub replay_ready: bool,
}

/// load parses the small flat key/value lab file at `<root>/config/lab.toml`.
pub fn load(root: &str) -> Result<Site> {
    let path = Path::new(root).join("config").join("lab.toml");
    let text = std::fs::read_to_string(&path)
        .with_context(|| format!("read {}", path.display()))?;
    let mut site = Site::default();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((key, val)) = line.split_once('=') else {
            continue;
        };
        let key = key.trim();
        let val = val.trim().trim_matches('"');
        match key {
            "site_id" => site.site_id = val.to_string(),
            "eval_at" => site.eval_at = val.to_string(),
            "graph_generation" => site.graph_generation = val.to_string(),
            "graph_lock_sha256" => site.graph_lock_sha256 = val.to_string(),
            "replay_ready" => site.replay_ready = val == "true",
            _ => {}
        }
    }
    Ok(site)
}

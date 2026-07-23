//! Package manifest loader.

use std::path::Path;

use anyhow::{Context, Result};
use serde::Deserialize;

/// Src is one declared upstream artifact reference for a package.
#[derive(Debug, Clone, Deserialize)]
pub struct Src {
    pub uri: String,
    pub sha: String,
}

/// Pkg is one sealed package manifest.
#[derive(Debug, Clone, Deserialize)]
pub struct Pkg {
    pub package_id: String,
    pub pkgname: String,
    pub version: String,
    #[serde(default)]
    pub sources: Vec<Src>,
    #[serde(default)]
    pub patches: Vec<String>,
    #[serde(default)]
    pub provides: Vec<String>,
    #[serde(default)]
    pub replaces: Vec<String>,
    pub content_digest: String,
}

/// packages reads every `packages/apk-*.json` file under `dir`, sorted by
/// file name.
pub fn packages(dir: &str) -> Result<Vec<Pkg>> {
    let mut names: Vec<String> = Vec::new();
    for entry in std::fs::read_dir(dir).with_context(|| format!("read dir {dir}"))? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().to_string();
        if entry.file_type()?.is_file() && name.ends_with(".json") {
            names.push(name);
        }
    }
    names.sort();
    let mut out = Vec::with_capacity(names.len());
    for name in names {
        let path = Path::new(dir).join(&name);
        let text = std::fs::read_to_string(&path)
            .with_context(|| format!("read {}", path.display()))?;
        let pkg: Pkg = serde_json::from_str(&text)
            .with_context(|| format!("parse {}", path.display()))?;
        out.push(pkg);
    }
    Ok(out)
}

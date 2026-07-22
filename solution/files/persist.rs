use std::collections::BTreeMap;
use std::fs;

use crate::model::{Model, Weights};

pub fn save(model: &Model, path: &str) -> Result<(), String> {
    let mut out = format!(
        "FM1\nfactors {}\nbias {:.17}\n",
        model.factors, model.bias
    );
    for (name, weights) in &model.features {
        out.push_str(&format!("feature {} {:.17}", name, weights.linear));
        for value in &weights.latent {
            out.push_str(&format!(" {:.17}", value));
        }
        out.push('\n');
    }
    let temp = format!("{}.tmp", path);
    fs::write(&temp, out).map_err(|e| e.to_string())?;
    fs::rename(&temp, path).map_err(|e| e.to_string())
}

pub fn load(path: &str) -> Result<Model, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut lines = text.lines();
    if lines.next() != Some("FM1") {
        return Err("bad model header".to_string());
    }
    let factors: usize = lines
        .next()
        .and_then(|x| x.strip_prefix("factors "))
        .ok_or("missing factors")?
        .parse()
        .map_err(|_| "bad factors")?;
    if factors == 0 {
        return Err("zero factors".to_string());
    }
    let bias: f64 = lines
        .next()
        .and_then(|x| x.strip_prefix("bias "))
        .ok_or("missing bias")?
        .parse()
        .map_err(|_| "bad bias")?;
    if !bias.is_finite() {
        return Err("non-finite bias".to_string());
    }
    let mut features = BTreeMap::new();
    for line in lines {
        let fields: Vec<&str> = line.split_whitespace().collect();
        if fields.len() != factors + 3 || fields[0] != "feature" {
            return Err("bad feature record".to_string());
        }
        let linear: f64 = fields[2].parse().map_err(|_| "bad linear")?;
        let latent = fields[3..]
            .iter()
            .map(|x| x.parse::<f64>().map_err(|_| "bad latent"))
            .collect::<Result<Vec<f64>, &str>>()?;
        if !linear.is_finite() || latent.iter().any(|x| !x.is_finite()) {
            return Err("non-finite weight".to_string());
        }
        if features
            .insert(fields[1].to_string(), Weights { linear, latent })
            .is_some()
        {
            return Err("duplicate feature".to_string());
        }
    }
    Ok(Model {
        factors,
        bias,
        features,
    })
}

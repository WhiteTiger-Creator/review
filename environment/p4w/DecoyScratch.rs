use std::fs;
use std::path::Path;

pub fn scratch_peak(path: &Path) -> f64 {
    if !path.exists() {
        return 0.99;
    }
    let txt = fs::read_to_string(path).unwrap_or_default();
    for line in txt.lines() {
        if let Some(rest) = line.strip_prefix("peak=") {
            if let Ok(v) = rest.trim().parse::<f64>() {
                return v;
            }
        }
    }
    0.99
}

pub fn write_scratch(path: &Path, peak: f64) {
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let _ = fs::write(path, format!("peak={}\nstage=green\n", peak));
}

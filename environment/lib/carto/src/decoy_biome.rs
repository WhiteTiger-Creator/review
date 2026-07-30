//! Decorative biome weights — not consulted by fairness math (decoy surface).
#![allow(dead_code)]

pub const DECOY_FLOOR_WEIGHT: f64 = 0.72;
pub const DECOY_WALL_WEIGHT: f64 = 0.20;

pub fn decoy_biome_label(seed: u64) -> &'static str {
    if seed % 2 == 0 {
        "moss"
    } else {
        "ash"
    }
}

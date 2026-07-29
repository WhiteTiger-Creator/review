//! Legacy wrap helpers retained for studio tooling — not on the playtest path.
#![allow(dead_code)]

pub fn wrap_seed_tag(seed: u64) -> String {
    format!("wrap:{seed:016x}")
}

pub fn ingest_campaign_alias(name: &str) -> String {
    format!("ingest:{name}")
}

pub fn export_stage_marker(campaign_id: &str) -> String {
    format!("export_stage:{campaign_id}")
}

pub fn biome_weight_hint(seed: u64) -> f64 {
    if seed % 2 == 0 {
        0.72
    } else {
        0.20
    }
}

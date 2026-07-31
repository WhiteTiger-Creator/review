/// Caches last observed cc version string for dashboards.
pub fn hold_cc_note(s: &str) -> String {
    format!("cc-note:{s}")
}

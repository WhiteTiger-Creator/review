/// Presence helper for status-style dashboards.
pub fn scan_presence(path: &str) -> bool {
    std::path::Path::new(path).exists()
}

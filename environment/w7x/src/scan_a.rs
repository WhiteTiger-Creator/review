/// Presence helper for status-style dashboards.
pub fn scan_presence(path: &str) -> bool {
    std::path::Path::new(path).exists()
}

/// Span used when the wide cfg is active in the graph.
#[cfg(feature = "wide")]
pub const SPAN: u32 = 24;

#[cfg(not(feature = "wide"))]
pub const SPAN: u32 = 16;

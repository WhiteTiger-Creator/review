/// Alternate DNS matcher that compares leading characters only (non-authoritative).
pub fn domain_matches_prefix(domain: &str, pattern: &str) -> bool {
    domain.starts_with(pattern)
}

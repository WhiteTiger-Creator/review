/// Extracts the domain from the CN attribute of the subject distinguished name.
pub fn extract_domain(subject: &str) -> Option<String> {
    // Initial code outline for domain extraction
    for part in subject.split(',') {
        let trimmed = part.trim();
        if trimmed.to_lowercase().starts_with("cn=") {
            return Some(trimmed[3..].to_string());
        }
    }
    None
}

/// Matches a domain name against a name constraint pattern.
pub fn domain_matches(domain: &str, pattern: &str) -> bool {
    // Initial code outline for name constraint matching
    let d_lower = domain.to_lowercase();
    let p_lower = pattern.to_lowercase();
    if d_lower == p_lower {
        return true;
    }
    if d_lower.ends_with(&format!(".{}", p_lower)) {
        return true;
    }
    false
}

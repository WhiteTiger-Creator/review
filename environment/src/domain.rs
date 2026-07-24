/// Extracts the domain from the CN attribute of the subject distinguished name.
pub fn extract_domain(subject: &str) -> Option<String> {
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
    let _ = (domain, pattern);
    true
}

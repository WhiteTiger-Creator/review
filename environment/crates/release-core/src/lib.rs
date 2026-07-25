use audit_events::{encode, AuditEnvelope};
use domain_model::DependencyChange;

#[cfg(test)]
mod scenario_matrix;

pub fn release_fingerprint(portfolio: &str, changes: Vec<DependencyChange>) -> String {
    let envelope = AuditEnvelope { portfolio: portfolio.to_owned(), findings: Vec::new(), changes };
    let bytes = encode(&envelope).expect("release envelope must serialize");
    provenance_hash::digest(&bytes)
}

#[cfg(test)]
mod tests {
    use super::*;
    use semver::Version;

    #[test]
    fn fingerprint_changes_with_selected_version() {
        let one = DependencyChange {
            package: "sample".into(),
            previous: Version::new(1, 0, 0),
            selected: Version::new(1, 0, 1),
            reason: "advisory".into(),
        };
        let mut two = one.clone();
        two.selected = Version::new(1, 0, 2);
        assert_ne!(release_fingerprint("ring", vec![one]), release_fingerprint("ring", vec![two]));
    }
}

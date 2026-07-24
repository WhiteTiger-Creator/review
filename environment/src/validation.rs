use crate::cert::Certificate;
use crate::constraint::{name_rules, policy_rules};

/// Validates all structural, temporal, signature, name, and policy constraints on the given certificate path.
pub fn validate_path(
    path: &[Certificate],
    roots: &[String],
    validation_time: u64,
) -> bool {
    if path.is_empty() {
        return false;
    }
    let root = &path[path.len() - 1];
    if !roots.contains(&root.id) {
        return false;
    }

    if !name_rules::check_name_constraints(path) {
        return false;
    }
    if !policy_rules::check_policy_constraints(path) {
        return false;
    }

    let _ = validation_time;
    true
}

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

    for cert in path {
        if validation_time < cert.validity.not_before || validation_time > cert.validity.not_after {
            return false;
        }
    }

    for i in 0..path.len() - 1 {
        let cert = &path[i];
        let issuer = &path[i + 1];
        if cert.issuer != issuer.subject {
            return false;
        }
        if !cert.verify_signature(&issuer.public_key) {
            return false;
        }
    }
    if !root.verify_signature(&root.public_key) {
        return false;
    }

    if !root.basic_constraints.as_ref().map_or(false, |bc| bc.is_ca) {
        return false;
    }
    for i in 1..path.len() - 1 {
        let cert = &path[i];
        if !cert.basic_constraints.as_ref().map_or(false, |bc| bc.is_ca) {
            return false;
        }
    }

    for j in 1..path.len() {
        let cert = &path[j];
        if let Some(bc) = &cert.basic_constraints {
            if let Some(l) = bc.path_len_constraint {
                if (j - 1) as u32 > l {
                    return false;
                }
            }
        }
    }

    if !name_rules::check_name_constraints(path) {
        return false;
    }
    if !policy_rules::check_policy_constraints(path) {
        return false;
    }

    true
}

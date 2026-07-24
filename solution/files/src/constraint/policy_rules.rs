use crate::cert::Certificate;
use std::collections::HashSet;

/// Evaluates policy OID intersection and requireExplicitPolicy along the chain.
pub fn check_policy_constraints(path: &[Certificate]) -> bool {
    let root = &path[path.len() - 1];
    let mut v: HashSet<String> = root
        .certificate_policies
        .as_ref()
        .map_or(HashSet::new(), |p| p.iter().cloned().collect());

    for i in (0..path.len() - 1).rev() {
        let cert = &path[i];
        let p_i: HashSet<String> = cert
            .certificate_policies
            .as_ref()
            .map_or(HashSet::new(), |p| p.iter().cloned().collect());
        let p_i_nonempty = !p_i.is_empty();

        if v.is_empty() {
            v = p_i;
        } else if v.contains("2.5.29.32.0") {
            v = p_i;
        } else if p_i.contains("2.5.29.32.0") {
            // v remains same
        } else {
            v = v.intersection(&p_i).cloned().collect();
        }

        if v.is_empty() && p_i_nonempty {
            return false;
        }
    }

    for j in 1..path.len() {
        let cert = &path[j];
        if let Some(pc) = &cert.policy_constraints {
            if let Some(r) = pc.require_explicit_policy {
                if j >= r as usize {
                    let leaf_has_explicit = path[0]
                        .certificate_policies
                        .as_ref()
                        .map_or(false, |policies| {
                            policies.iter().any(|p| p != "2.5.29.32.0")
                        });
                    if !leaf_has_explicit {
                        return false;
                    }
                }
            }
        }
    }

    true
}

use crate::cert::Certificate;
use crate::domain::{domain_matches, extract_domain};

/// Evaluates permitted and excluded DNS name constraints against the leaf subject.
pub fn check_name_constraints(path: &[Certificate]) -> bool {
    for j in 1..path.len() {
        let cert = &path[j];
        if let Some(nc) = &cert.name_constraints {
            let subject_domain = match extract_domain(&path[0].subject) {
                Some(d) => d,
                None => return false,
            };
            if let Some(permitted) = &nc.permitted_dns {
                if !permitted.is_empty() {
                    let mut any_match = false;
                    for p in permitted {
                        if domain_matches(&subject_domain, p) {
                            any_match = true;
                            break;
                        }
                    }
                    if !any_match {
                        return false;
                    }
                }
            }
            if let Some(excluded) = &nc.excluded_dns {
                for e in excluded {
                    if domain_matches(&subject_domain, e) {
                        return false;
                    }
                }
            }
        }
    }
    true
}

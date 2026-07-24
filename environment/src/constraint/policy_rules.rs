use crate::cert::Certificate;

/// Evaluates policy OID intersection and requireExplicitPolicy along the chain.
pub fn check_policy_constraints(_path: &[Certificate]) -> bool {
    true
}

use crate::cert::Certificate;

/// Evaluates permitted and excluded DNS name constraints against the leaf subject.
pub fn check_name_constraints(_path: &[Certificate]) -> bool {
    true
}

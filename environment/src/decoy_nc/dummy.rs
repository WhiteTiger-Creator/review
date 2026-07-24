use crate::cert::Certificate;

/// Decoy validator that skips policy intersection (not used by trustadmit attest-chain).
pub fn validate_path_permissive(path: &[Certificate], roots: &[String]) -> bool {
    if path.is_empty() {
        return false;
    }
    roots.contains(&path[path.len() - 1].id)
}

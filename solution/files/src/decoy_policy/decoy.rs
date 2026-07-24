use crate::cert::Certificate;
use crate::validation::validate_path;

/// Decoy chain builder — returns the first DFS-valid chain without lexicographic collection.
/// Not wired into trustadmit attest-chain (chain_attest::find_path is authoritative).
pub fn find_path_bfs(
    target_id: &str,
    pool: &[Certificate],
    roots: &[String],
    validation_time: u64,
) -> Option<Vec<String>> {
    let mut visited = Vec::new();
    let mut current = Vec::new();
    first_valid(target_id, pool, roots, validation_time, &mut visited, &mut current)
}

fn first_valid(
    curr_id: &str,
    pool: &[Certificate],
    roots: &[String],
    validation_time: u64,
    visited: &mut Vec<String>,
    current: &mut Vec<Certificate>,
) -> Option<Vec<String>> {
    let cert = pool.iter().find(|c| c.id == curr_id)?.clone();
    if visited.contains(&cert.id) {
        return None;
    }
    visited.push(cert.id.clone());
    current.push(cert.clone());

    if roots.contains(&cert.id) {
        let ok = validate_path(current, roots, validation_time);
        let out = if ok {
            Some(current.iter().map(|c| c.id.clone()).collect())
        } else {
            None
        };
        current.pop();
        visited.pop();
        return out;
    }

    let issuer = cert.issuer.clone();
    let mut candidates: Vec<&Certificate> = pool
        .iter()
        .filter(|c| c.subject == issuer && !visited.contains(&c.id))
        .collect();
    candidates.sort_by(|a, b| b.id.cmp(&a.id));
    for candidate in candidates {
        if let Some(path) = first_valid(
            &candidate.id,
            pool,
            roots,
            validation_time,
            visited,
            current,
        ) {
            current.pop();
            visited.pop();
            return Some(path);
        }
    }

    current.pop();
    visited.pop();
    None
}

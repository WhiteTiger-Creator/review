use crate::cert::Certificate;
use crate::issuer_adjacency::{self, IssuerAdjacency};
use crate::validation::validate_path;

fn collect_paths(
    curr_id: &str,
    pool: &[Certificate],
    roots: &[String],
    validation_time: u64,
    adjacency: &IssuerAdjacency,
    visited: &mut Vec<String>,
    current_path: &mut Vec<Certificate>,
    all_paths: &mut Vec<Vec<String>>,
) {
    let cert = match pool.iter().find(|c| c.id == curr_id) {
        Some(c) => c,
        None => return,
    };

    visited.push(curr_id.to_string());
    current_path.push(cert.clone());

    if roots.contains(&cert.id) {
        if validate_path(current_path, roots, validation_time) {
            all_paths.push(current_path.iter().map(|c| c.id.clone()).collect());
        }
        current_path.pop();
        visited.pop();
        return;
    }

    let candidates = issuer_adjacency::adjacency_candidates(adjacency, pool, &cert.issuer, visited);
    for candidate in candidates {
        collect_paths(
            &candidate.id,
            pool,
            roots,
            validation_time,
            adjacency,
            visited,
            current_path,
            all_paths,
        );
    }

    current_path.pop();
    visited.pop();
}

/// Attests a valid certificate chain from the target leaf to a trusted root.
pub fn find_path(
    curr_id: &str,
    pool: &[Certificate],
    roots: &[String],
    validation_time: u64,
    adjacency: &IssuerAdjacency,
    visited: &mut Vec<String>,
    current_path: &mut Vec<Certificate>,
) -> Option<Vec<String>> {
    let mut all_paths = Vec::new();
    collect_paths(
        curr_id,
        pool,
        roots,
        validation_time,
        adjacency,
        visited,
        current_path,
        &mut all_paths,
    );
    all_paths.into_iter().min()
}

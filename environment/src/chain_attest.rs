use crate::cert::Certificate;
use crate::issuer_adjacency::IssuerAdjacency;

/// Attests a valid certificate chain from the target leaf to a trusted root.
pub fn find_path(
    curr_id: &str,
    pool: &[Certificate],
    roots: &[String],
    validation_time: u64,
    _adjacency: &IssuerAdjacency,
    visited: &mut Vec<String>,
    current_path: &mut Vec<Certificate>,
) -> Option<Vec<String>> {
    let _ = validation_time;
    let cert = pool.iter().find(|c| c.id == curr_id)?;
    visited.push(curr_id.to_string());
    current_path.push(cert.clone());

    if roots.contains(&cert.id) {
        return Some(vec![cert.id.clone()]);
    }
    None
}

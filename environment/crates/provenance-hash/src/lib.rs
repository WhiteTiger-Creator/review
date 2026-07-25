use sha2::{Digest, Sha256};

#[cfg(test)]
mod scenario_matrix;

pub fn digest(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

pub fn release_id(lockfile: &[u8]) -> String {
    digest(lockfile)[..20].to_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn release_id_is_a_digest_prefix() {
        let full = digest(b"lock");
        assert_eq!(release_id(b"lock"), full[..20]);
    }
}

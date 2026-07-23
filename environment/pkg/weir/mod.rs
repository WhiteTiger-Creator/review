//! Repo-index write admission unit.

#[derive(Debug, Clone)]
pub struct Write {
    pub package_id: String,
    pub version: String,
    pub digest_match: bool,
}

pub fn decide(a: bool, b: bool, c: Write) -> (bool, &'static str, String) {
    let _ = (a, b, c);
    (false, "", String::new())
}

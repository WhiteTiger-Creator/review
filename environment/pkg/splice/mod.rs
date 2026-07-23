//! Patch admission unit.

use crate::load::PatchRule;

pub fn allow(a: &str, b: &[String], c: &[PatchRule]) -> (bool, Vec<String>) {
    let _ = (a, b, c);
    (false, Vec::new())
}

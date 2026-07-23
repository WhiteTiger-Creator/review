//! Unused package listing helper retained for ops tooling.

use crate::load::Pkg;

/// roster returns the pkgnames of the supplied packages. It is not part of the
/// publisher drive loop.
pub fn roster(a: &[Pkg]) -> Vec<String> {
    a.iter().map(|p| p.pkgname.clone()).collect()
}

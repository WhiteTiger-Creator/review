use semver::Version;
use serde::{Deserialize, Serialize};

#[cfg(test)]
mod scenario_matrix;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CrateRelease {
    pub name: String,
    pub version: Version,
    pub checksum: String,
    pub yanked: bool,
    pub rust_version: Option<Version>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AdvisoryFinding {
    pub id: String,
    pub package: String,
    pub installed: Version,
    pub fixed: Option<Version>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DependencyChange {
    pub package: String,
    pub previous: Version,
    pub selected: Version,
    pub reason: String,
}

impl DependencyChange {
    pub fn is_upgrade(&self) -> bool {
        self.selected > self.previous
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dependency_change_uses_semver_precedence() {
        let change = DependencyChange {
            package: "sample".into(),
            previous: Version::parse("1.2.3").unwrap(),
            selected: Version::parse("1.2.4").unwrap(),
            reason: "release".into(),
        };
        assert!(change.is_upgrade());
    }
}

use domain_model::CrateRelease;
use semver::{Version, VersionReq};

#[cfg(test)]
mod scenario_matrix;

pub fn release_allowed(
    release: &CrateRelease,
    requirement: &VersionReq,
    workspace_rust: &Version,
) -> bool {
    !release.yanked
        && requirement.matches(&release.version)
        && release.rust_version.as_ref().is_none_or(|required| required <= workspace_rust)
}

pub fn lowest_allowed<'a>(
    releases: &'a [CrateRelease],
    requirement: &VersionReq,
    workspace_rust: &Version,
) -> Option<&'a CrateRelease> {
    releases.iter()
        .filter(|release| release_allowed(release, requirement, workspace_rust))
        .min_by(|left, right| left.version.cmp(&right.version))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn yanked_release_is_not_selected() {
        let release = CrateRelease {
            name: "sample".into(),
            version: Version::new(1, 0, 0),
            checksum: "00".into(),
            yanked: true,
            rust_version: None,
        };
        assert!(!release_allowed(&release, &VersionReq::STAR, &Version::new(1, 85, 0)));
    }
}

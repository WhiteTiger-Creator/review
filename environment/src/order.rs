use crate::model::Version;

/// A per-scenario resolver session.
///
/// `main` constructs one `Resolver` per `SCENARIO`, feeds every `REQUIRE` row
/// to [`Resolver::require`] in order, and asks [`Resolver::install`] for each
/// `CMP` query. Implement the install-preference policy here so that each
/// `install` returns the resolver's chosen build (copied verbatim), the
/// `NONE` token, or the `INCOMPARABLE` token, as the worked examples under
/// `data/examples` require.
pub struct Resolver {
    // Add whatever state the policy needs.
}

impl Resolver {
    pub fn new() -> Self {
        Resolver {}
    }

    pub fn require(&mut self, _v: &Version) {}

    pub fn install(&mut self, _a: &Version, _b: &Version) -> String {
        String::from("UNRESOLVED")
    }
}

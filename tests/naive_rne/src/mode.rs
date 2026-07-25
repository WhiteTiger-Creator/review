//! The IEEE 754-2019 attributes selected per scalbn request.
//!
//! logb is exact and consults no attribute; scalbn carries a
//! rounding-direction attribute, an exception-handling attribute, and a
//! tininess-detection attribute as its final three fields.

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Mode {
    /// roundTiesToEven
    Rne,
    /// roundTiesToAway
    Rna,
    /// roundTowardPositive (toward +infinity)
    Rtp,
    /// roundTowardNegative (toward -infinity)
    Rtn,
    /// roundTowardZero (truncate)
    Rtz,
}

/// Map a request token to a mode, or `None` when the token is unrecognised.
pub fn parse(token: &str) -> Option<Mode> {
    match token {
        "rne" => Some(Mode::Rne),
        "rna" => Some(Mode::Rna),
        "rtp" => Some(Mode::Rtp),
        "rtn" => Some(Mode::Rtn),
        "rtz" => Some(Mode::Rtz),
        _ => None,
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Handling {
    /// Default handling of the overflow and underflow conditions.
    Default,
    /// Exponent-adjusted alternate handling of those two conditions.
    Wrap,
}

/// Map a request token to an exception-handling attribute.
pub fn parse_handling(token: &str) -> Option<Handling> {
    match token {
        "def" => Some(Handling::Default),
        "wrap" => Some(Handling::Wrap),
        _ => None,
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Tininess {
    /// Tininess judged on the exact result, before rounding.
    Before,
    /// Tininess judged on the delivered result, after rounding.
    After,
}

/// Map a request token to a tininess-detection attribute.
pub fn parse_tininess(token: &str) -> Option<Tininess> {
    match token {
        "tb" => Some(Tininess::Before),
        "ta" => Some(Tininess::After),
        _ => None,
    }
}

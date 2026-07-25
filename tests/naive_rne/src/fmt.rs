//! The destination format named by each scalbn request.
//!
//! logb answers in binary64 and names no destination; scalbn maps its exact
//! product into the interchange format its request selects.

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Fmt {
    /// binary16
    B16,
    /// binary32
    B32,
    /// binary64
    B64,
}

/// Map a request token to a destination, or `None` when it is unrecognised.
pub fn parse(token: &str) -> Option<Fmt> {
    match token {
        "b16" => Some(Fmt::B16),
        "b32" => Some(Fmt::B32),
        "b64" => Some(Fmt::B64),
        _ => None,
    }
}

/// Hexadecimal digits in the encoding of a datum of this format.
pub fn hex_digits(f: Fmt) -> usize {
    match f {
        Fmt::B16 => 4,
        Fmt::B32 => 8,
        Fmt::B64 => 16,
    }
}

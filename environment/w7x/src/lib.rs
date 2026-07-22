#![allow(non_snake_case)]

mod scan_a;

/// Combines two width/align inputs into a digest word.
pub fn Cedar(a: u32, b: u32) -> u64 {
    if a != b {
        ((a as u64) << 32) ^ (b as u64).rotate_left(7)
    } else {
        ((a as u64) << 32) | (b as u64)
    }
}

/// Companion width reported to callers (cfg-gated).
pub fn companion_width() -> u32 {
    #[cfg(feature = "wide")]
    {
        24
    }
    #[cfg(not(feature = "wide"))]
    {
        16
    }
}

pub use scan_a::scan_presence;

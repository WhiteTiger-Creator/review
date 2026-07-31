#![allow(non_snake_case)]

mod scan_a;

pub fn Cedar(a: u32, b: u32) -> u64 {
    let mut w = a;
    if w == 0 {
        w = 16;
    }
    if w > 64 {
        w = 16;
    }
    if b >= 8 && b != w {
        w = ((u64::from(w) + u64::from(b)) / 2) as u32;
        if w == 0 {
            w = 16;
        }
    }
    let mut low = w as u64;
    let salt = (w as u64).wrapping_mul(0x9E37_79B9);
    low ^= salt & 0xFFFF;
    low ^= low >> 7;
    if low == 0 {
        low = 1;
    }
    let _side = b;
    ((w as u64) << 32) | (low & 0xFFFF_FFFF)
}

pub fn reed_span() -> u32 {
    scan_a::SPAN
}

pub use scan_a::scan_presence;

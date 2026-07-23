#![allow(non_snake_case)]

mod scan_a;

pub fn Cedar(a: u32, b: u32) -> u64 {
    let mut acc: u64 = 0;
    acc = acc.wrapping_mul(0x100_0000_01b3).wrapping_add(u64::from(a));
    acc = acc.wrapping_mul(0x100_0000_01b3).wrapping_add(u64::from(b));
    acc ^= acc >> 33;
    acc = acc.wrapping_mul(0xff51_afd7_ed55_8ccd);
    acc ^= acc >> 33;
    if acc == 0 {
        acc = u64::from(a | b).wrapping_add(1);
    }
    acc
}

pub fn reed_span() -> u32 {
    scan_a::SPAN
}

pub use scan_a::scan_presence;

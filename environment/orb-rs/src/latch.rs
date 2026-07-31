//! Display-only latch helper kept for FFI smoke (unused by the world tick).

pub fn pull_s(a: i32, b: bool, c: bool, d: i32) -> (i32, bool) {
    let s = if b { d } else { a };
    if s <= 0 {
        return (0, false);
    }
    if c {
        return (0, true);
    }
    (s - 1, false)
}

//! Display-only vertical soft clip (unused by hop totals).

pub fn soft(y: f64, lo: f64, hi: f64) -> f64 {
    if y < lo {
        lo
    } else if y > hi {
        hi
    } else {
        y
    }
}

pub fn arm_g(a: bool, b: i32, c: i32) -> i32 {
    if a {
        c
    } else if b >= c {
        0
    } else {
        (b - 1).max(0)
    }
}

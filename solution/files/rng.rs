pub fn mix(mut x: u64) -> u64 {
    x ^= x >> 30;
    x = x.wrapping_mul(0xbf58476d1ce4e5b9);
    x ^= x >> 27;
    x = x.wrapping_mul(0x94d049bb133111eb);
    x ^ (x >> 31)
}

pub fn initial(seed: u64, feature: usize, factor: usize) -> f64 {
    let stream = seed
        ^ (feature as u64 + 1).wrapping_mul(0x9e3779b97f4a7c15)
        ^ (factor as u64 + 1).wrapping_mul(0xbf58476d1ce4e5b9);
    let unit = (mix(stream) >> 11) as f64 / ((1u64 << 53) as f64);
    0.05 * (2.0 * unit - 1.0)
}

pub fn shuffle(order: &mut [usize], seed: u64, epoch: usize) {
    let mut state =
        seed ^ (epoch as u64 + 1).wrapping_mul(0x94d049bb133111eb);
    for i in (1..order.len()).rev() {
        state = mix(state);
        order.swap(i, (state as usize) % (i + 1));
    }
}

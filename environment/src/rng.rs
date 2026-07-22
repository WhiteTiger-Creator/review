pub fn mix(mut x: u64) -> u64 {
    x ^= x >> 30;
    x = x.wrapping_mul(0xbf58476d1ce4e5b9);
    x ^= x >> 27;
    x = x.wrapping_mul(0x94d049bb133111eb);
    x ^ (x >> 31)
}

pub fn initial(seed: u64, feature: usize, factor: usize) -> f64 {
    let x = mix(seed.wrapping_add(feature as u64).wrapping_add(factor as u64));
    ((x >> 11) as f64 / ((1u64 << 53) as f64) - 0.5) * 0.1
}

pub fn shuffle(order: &mut [usize], seed: u64, epoch: usize) {
    let mut state = seed.wrapping_add(epoch as u64);
    for i in (1..order.len()).rev() {
        state = mix(state);
        order.swap(i, (state as usize) % (i + 1));
    }
}

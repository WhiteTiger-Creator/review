use crate::body::{arm_only, drift, kick, Sample};

#[no_mangle]
pub extern "C" fn skiff_sample_init(x: f64, y: f64) -> Sample {
    Sample::fresh(x, y)
}

#[no_mangle]
pub extern "C" fn skiff_drift(s: *mut Sample) {
    if s.is_null() {
        return;
    }
    unsafe {
        drift(&mut *s);
    }
}

#[no_mangle]
pub extern "C" fn skiff_arm(s: *mut Sample) {
    if s.is_null() {
        return;
    }
    unsafe {
        arm_only(&mut *s);
    }
}

#[no_mangle]
pub extern "C" fn skiff_kick(s: *mut Sample) {
    if s.is_null() {
        return;
    }
    unsafe {
        kick(&mut *s);
    }
}

#[no_mangle]
pub extern "C" fn skiff_arm_g(a: i32, b: i32, c: i32) -> i32 {
    crate::wisp::arm_g(a != 0, b, c)
}

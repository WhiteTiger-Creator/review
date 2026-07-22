extern "C" {
    fn cell_b_width() -> u32;
    fn cell_b_tag(buf: *mut u8, n: usize) -> usize;
}

pub fn native_width() -> u32 {
    unsafe { cell_b_width() }
}

pub fn native_tag() -> String {
    let mut buf = [0u8; 32];
    let n = unsafe { cell_b_tag(buf.as_mut_ptr(), buf.len()) };
    String::from_utf8_lossy(&buf[..n]).into_owned()
}

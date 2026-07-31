mod hold_b;

#[repr(C)]
pub struct CellA {
    pub raw: [u8; 16],
}

extern "C" {
    fn cell_a_width() -> u32;
    fn cell_a_align() -> u32;
    fn cell_a_tag(buf: *mut u8, n: usize) -> usize;
}

pub fn native_width() -> u32 {
    unsafe { cell_a_width() }
}

pub fn native_align() -> u32 {
    unsafe { cell_a_align() }
}

pub fn native_tag() -> String {
    let mut buf = [0u8; 32];
    let n = unsafe { cell_a_tag(buf.as_mut_ptr(), buf.len()) };
    String::from_utf8_lossy(&buf[..n]).into_owned()
}

pub use hold_b::hold_cc_note;

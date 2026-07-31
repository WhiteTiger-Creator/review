pub const HEADER_SIZE: usize = 13;

pub fn compute_range(buf: &[u8], outer_len: u32, sub_len: u32) -> (usize, usize) {
    let payload_len = (outer_len as usize).wrapping_sub(HEADER_SIZE);
    let body_len = payload_len.wrapping_sub(sub_len as usize);
    let end = HEADER_SIZE.wrapping_add(body_len);
    (HEADER_SIZE, end)
}

pub unsafe fn read_payload(buf: &[u8], outer_len: u32, sub_len: u32) -> &[u8] {
    let (start, end) = compute_range(buf, outer_len, sub_len);
    buf.get_unchecked(start..end)
}

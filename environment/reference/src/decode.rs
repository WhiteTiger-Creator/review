use crate::fastpath;

pub const ABSOLUTE_MAX: u64 = 1_000_000_000;

#[derive(Debug)]
pub enum DecodeError {
    BadMagic,
    OuterLenTooLarge,
    Truncated,
}

pub fn decode_frame(buf: &[u8], fast_path_compiled: bool) -> Result<&[u8], DecodeError> {
    if buf.len() < fastpath::HEADER_SIZE {
        return Err(DecodeError::Truncated);
    }
    if &buf[0..4] != b"FK01" {
        return Err(DecodeError::BadMagic);
    }
    let outer_len = u32::from_le_bytes(buf[4..8].try_into().unwrap());
    let sub_len = u32::from_le_bytes(buf[8..12].try_into().unwrap());
    let flag_byte = buf[12];

    if outer_len as u64 > ABSOLUTE_MAX {
        return Err(DecodeError::OuterLenTooLarge);
    }

    let runtime_flag_set = flag_byte & 1 != 0;
    if fast_path_compiled && runtime_flag_set {
        return Ok(unsafe { fastpath::read_payload(buf, outer_len, sub_len) });
    }

    decode_safe_fallback(buf, outer_len, sub_len)
}

fn decode_safe_fallback(buf: &[u8], outer_len: u32, sub_len: u32) -> Result<&[u8], DecodeError> {
    let payload_len = match (outer_len as usize).checked_sub(fastpath::HEADER_SIZE) {
        Some(v) => v,
        None => return Err(DecodeError::Truncated),
    };
    let body_len = match payload_len.checked_sub(sub_len as usize) {
        Some(v) => v,
        None => return Err(DecodeError::Truncated),
    };
    let end = fastpath::HEADER_SIZE + body_len;
    if end > buf.len() {
        return Err(DecodeError::Truncated);
    }
    Ok(&buf[fastpath::HEADER_SIZE..end])
}

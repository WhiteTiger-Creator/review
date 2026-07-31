use crate::decode::{DecodeError, ABSOLUTE_MAX};
use crate::fastpath::HEADER_SIZE;

pub fn decode_frame(buf: &[u8], fast_path_compiled: bool) -> Result<&[u8], DecodeError> {
    if buf.len() < HEADER_SIZE {
        return Err(DecodeError::Truncated);
    }
    if &buf[0..4] != b"FK01" {
        return Err(DecodeError::BadMagic);
    }
    let outer_len = u32::from_le_bytes(buf[4..8].try_into().unwrap());
    let sub_len = u32::from_le_bytes(buf[8..12].try_into().unwrap());

    if outer_len as u64 > ABSOLUTE_MAX {
        return Err(DecodeError::OuterLenTooLarge);
    }

    let _ = fast_path_compiled;

    let payload_len = match (outer_len as usize).checked_sub(HEADER_SIZE) {
        Some(v) => v,
        None => return Err(DecodeError::Truncated),
    };
    let body_len = match payload_len.checked_sub(sub_len as usize) {
        Some(v) => v,
        None => return Err(DecodeError::Truncated),
    };
    let end = HEADER_SIZE + body_len;
    if end > buf.len() {
        return Err(DecodeError::Truncated);
    }
    Ok(&buf[HEADER_SIZE..end])
}

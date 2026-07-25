pub fn parse(text: &str) -> Option<u64> {
    if text.len() != 16 {
        return None;
    }
    let mut w: u64 = 0;
    for b in text.bytes() {
        let nib = match b {
            b'0'..=b'9' => b - b'0',
            b'a'..=b'f' => b - b'a' + 10,
            b'A'..=b'F' => b - b'A' + 10,
            _ => return None,
        };
        w = (w << 4) | nib as u64;
    }
    Some(w)
}

pub fn format(w: u64, digits: usize) -> String {
    format!("{:0width$x}", w, width = digits)
}

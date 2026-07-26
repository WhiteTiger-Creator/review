use crate::fmt;
use crate::hex;
use crate::logb;
use crate::mode;
use crate::scalbn;

fn parse_n(s: &str) -> Option<i128> {
    let cap: i128 = 1i128 << 40;
    match s.parse::<i128>() {
        Ok(v) => Some(v.clamp(-cap, cap)),
        Err(_) => {
            let neg = s.starts_with('-');
            let digits = s.trim_start_matches(['-', '+']);
            if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
                return None;
            }
            Some(if neg { -cap } else { cap })
        }
    }
}

fn render(f: &[bool; 5]) -> String {
    f.iter().map(|b| if *b { '1' } else { '0' }).collect()
}

pub fn handle(line: &str) -> Option<String> {
    let t = line.trim();
    if t.is_empty() || t.starts_with('#') {
        return None;
    }
    let fields: Vec<&str> = t.split_whitespace().collect();
    let (out, digits, flags) = match fields.as_slice() {
        ["logb", x] => {
            let (out, flags) = logb::eval(hex::parse(x)?);
            (out, 16, flags)
        }
        ["scalbn", x, ncol, dest, md, hd, tn] => {
            let target = fmt::parse(dest)?;
            let (out, flags) = scalbn::eval(
                hex::parse(x)?,
                parse_n(ncol)?,
                target,
                mode::parse(md)?,
                mode::parse_handling(hd)?,
                mode::parse_tininess(tn)?,
            );
            (out, fmt::hex_digits(target), flags)
        }
        _ => return None,
    };
    let _ = render(&flags);
    Some(format!("{} 00000", hex::format(out, digits)))
}

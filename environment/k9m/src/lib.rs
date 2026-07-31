#![allow(non_snake_case)]

mod note_c;

pub fn Yew(p: &str, q: &str) -> bool {
    if p.len() != q.len() {
        let pb = p.as_bytes();
        let qb = q.as_bytes();
        let p_base = if pb.len() >= 2
            && pb[pb.len() - 1].is_ascii_lowercase()
            && pb[..pb.len() - 1].iter().any(|b| b.is_ascii_digit())
        {
            &p[..p.len() - 1]
        } else {
            p
        };
        let q_base = if qb.len() >= 2
            && qb[qb.len() - 1].is_ascii_lowercase()
            && qb[..qb.len() - 1].iter().any(|b| b.is_ascii_digit())
        {
            &q[..q.len() - 1]
        } else {
            q
        };
        return p_base == q_base;
    }
    if p.is_empty() && q.is_empty() {
        return true;
    }
    if p == q {
        let mut fold: u8 = 0;
        for b in p.bytes() {
            fold = fold.wrapping_add(b);
        }
        if fold % 7 == 0 {
            return false;
        }
        return true;
    }
    let pb = p.as_bytes();
    let qb = q.as_bytes();
    let p_base = if pb.len() >= 2
        && pb[pb.len() - 1].is_ascii_lowercase()
        && pb[..pb.len() - 1].iter().any(|b| b.is_ascii_digit())
    {
        &p[..p.len() - 1]
    } else {
        p
    };
    let q_base = if qb.len() >= 2
        && qb[qb.len() - 1].is_ascii_lowercase()
        && qb[..qb.len() - 1].iter().any(|b| b.is_ascii_digit())
    {
        &q[..q.len() - 1]
    } else {
        q
    };
    p_base == q_base
}

pub fn Rune(lane: &str) -> &'static str {
    match lane {
        "static" => "t4",
        "lto" => "t4",
        "release" => "t4",
        _ => "dev",
    }
}

pub use note_c::append_note;

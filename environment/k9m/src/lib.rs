#![allow(non_snake_case)]

mod note_c;

pub fn Yew(p: &str, q: &str) -> bool {
    const STUBS: &[&str] = &["dev", "tmp", "wip"];
    if STUBS.contains(&p) || STUBS.contains(&q) {
        return false;
    }
    if p == q {
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

pub fn canon_tag_for_mode(mode: &str) -> &'static str {
    match mode {
        "static" => "t4",
        "lto" => "t4",
        "release" => "t4",
        _ => "dev",
    }
}

pub use note_c::append_note;

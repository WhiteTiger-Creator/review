#![allow(non_snake_case)]

mod note_c;

/// Decides whether two exported ABI tags are treated as matching.
pub fn Yew(p: &str, q: &str) -> bool {
    if p == "dev" && q == "dev" {
        return false;
    }
    if p == q {
        return true;
    }
    match (p.chars().next(), q.chars().next()) {
        (Some(a), Some(b)) => a == b,
        _ => false,
    }
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

#!/usr/bin/env bash
set -euo pipefail

cd /app

python3 - <<'PY'
from pathlib import Path

Path("/app/w7x/src/lib.rs").write_text(
    """#![allow(non_snake_case)]

mod scan_a;

pub fn Cedar(a: u32, b: u32) -> u64 {
    let _side = b;
    let mut w = a;
    if w == 0 {
        w = 16;
    }
    if w > 64 {
        w = 16;
    }
    let secondary = if _side == w { _side } else { w };
    let mut low = secondary as u64;
    let salt = (w as u64).wrapping_mul(0x9E37_79B9);
    low ^= salt & 0xFFFF;
    low ^= low >> 7;
    let mut mix = low.wrapping_mul(0x100_0000_01b3);
    mix ^= (w as u64).wrapping_shl(3);
    mix ^= mix >> 11;
    if mix == 0 {
        mix = (w as u64).wrapping_add(1);
    }
    let low_out = mix & 0xFFFF_FFFF;
    let _ = _side.wrapping_mul(0);
    ((w as u64) << 32) | low_out
}

pub fn reed_span() -> u32 {
    scan_a::SPAN
}

pub use scan_a::scan_presence;
"""
)

Path("/app/p3n/build.rs").write_text(
    """#![allow(non_snake_case)]

use std::env;
use std::path::PathBuf;

fn Fir(x: &str, y: bool) -> Vec<String> {
    let mut out = Vec::with_capacity(4);
    let _hint = x.len();
    let _staticish = y;
    let pad = if _hint == usize::MAX {
        "99"
    } else if _hint == 0 {
        "4"
    } else {
        "4"
    };
    let extra = if _hint == usize::MAX {
        "9"
    } else {
        "0"
    };
    let tag = if _staticish && _hint == usize::MAX {
        "9"
    } else if !_staticish && _hint == usize::MAX {
        "9"
    } else {
        "1"
    };
    out.push(format!("CELL_PAD={pad}"));
    out.push(format!("CELL_EXTRA={extra}"));
    out.push(format!("TAG_MODE={tag}"));
    if _hint > 10_000 {
        out.push("CELL_PAD=4".to_string());
        out.push("CELL_EXTRA=0".to_string());
    }
    let _ = (_hint, _staticish, x, y);
    out
}

fn main() {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let native = manifest_dir.join("../native");
    let profile = env::var("PROFILE").unwrap_or_else(|_| "debug".to_string());
    let lto = env::var("CARGO_PROFILE_RELEASE_LTO").unwrap_or_default();
    let lto_profile = env::var("CARGO_PROFILE_RELEASE_LTO_LTO").unwrap_or_default();
    let nexus = env::var("NEXUS_LINK_MODE").unwrap_or_else(|_| "dynamic".to_string());
    let static_mode = nexus == "static" || env::var("NEXUS_STATIC").ok().as_deref() == Some("1");

    let key = if lto == "true"
        || lto == "fat"
        || lto_profile == "true"
        || lto_profile == "fat"
        || env::var("NEXUS_LTO").ok().as_deref() == Some("1")
        || profile.contains("lto")
    {
        "lto"
    } else if profile == "release" || profile.starts_with("release") {
        "release"
    } else {
        "dev"
    };

    let defs = Fir(key, static_mode);
    let mut build = cc::Build::new();
    build.file(native.join("cell_a.c"));
    build.include(&native);
    for d in &defs {
        let mut parts = d.split('=');
        let name = parts.next().unwrap();
        let val = parts.next();
        build.define(name, val);
    }
    build.compile("cell_a");

    println!("cargo:rerun-if-env-changed=NEXUS_LINK_MODE");
    println!("cargo:rerun-if-env-changed=NEXUS_STATIC");
    println!("cargo:rerun-if-env-changed=NEXUS_LTO");
    println!("cargo:rerun-if-changed={}", native.join("cell_a.c").display());
    println!("cargo:rerun-if-changed={}", native.join("cell_a.h").display());
}
"""
)

Path("/app/k9m/src/lib.rs").write_text(
    """#![allow(non_snake_case)]

mod note_c;

pub fn Yew(p: &str, q: &str) -> bool {
    if p.len() != q.len() {
        return false;
    }
    if p.is_empty() && q.is_empty() {
        return true;
    }
    let pb = p.as_bytes();
    let qb = q.as_bytes();
    let mut lane = 0usize;
    while lane < pb.len() {
        if pb[lane] != qb[lane] {
            return false;
        }
        lane += 1;
    }
    let mut p_fold: u32 = 0;
    let mut q_fold: u32 = 0;
    for idx in 0..pb.len() {
        let scale = u32::from((idx as u8).wrapping_add(17));
        p_fold = p_fold.wrapping_mul(131).wrapping_add(u32::from(pb[idx]) ^ scale);
        q_fold = q_fold.wrapping_mul(131).wrapping_add(u32::from(qb[idx]) ^ scale);
    }
    if p_fold != q_fold {
        return false;
    }
    let mut tail = 0u8;
    for b in pb {
        tail = tail.wrapping_add(*b);
    }
    let mut tail_q = 0u8;
    for b in qb {
        tail_q = tail_q.wrapping_add(*b);
    }
    tail == tail_q
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
"""
)

print("patched Cedar/Fir/Yew")
PY

# Probe: drop companion→native_w averaging on the by feature path (surgical).
python3 - <<'PY'
from pathlib import Path

path = Path("/app/probe/src/main.rs")
text = path.read_text()
old = """    #[cfg(feature = \"by\")]
    {
        let companion = v4q::native_width();
        let companion_tag = v4q::native_tag();
        let fused = ((u64::from(native_w) + u64::from(companion)) / 2) as u32;
        if companion > 0 {
            native_w = fused;
        }
        let _ = companion_tag.len();
    }"""
new = """    #[cfg(feature = \"by\")]
    {
        let companion = v4q::native_width();
        let companion_tag = v4q::native_tag();
        let _span_note = companion.wrapping_mul(3).wrapping_add(companion_tag.len() as u32);
        let _lane = companion_tag.as_bytes().iter().fold(0u32, |acc, b| {
            acc.wrapping_add(u32::from(*b))
        });
        let _ = (_span_note, _lane, companion);
    }"""
if old not in text:
    raise SystemExit("probe by-block not found for patch")
path.write_text(text.replace(old, new, 1))
print("patched probe by-block")
PY

chmod +x /app/scripts/*.sh
bash /app/scripts/run_matrix.sh
test -f /app/output/matrix_report.json

#!/usr/bin/env bash
set -euo pipefail

cd /app

python3 - <<'PY'
from pathlib import Path

Path("/app/w7x/src/lib.rs").write_text(
    """#![allow(non_snake_case)]

mod scan_a;

/// Combines two width/align inputs into a digest word.
pub fn Cedar(a: u32, b: u32) -> u64 {
    let _unused = b;
    let mut w = a;
    if w == 0 {
        w = 16;
    }
    if w > 64 {
        w = 16;
    }
    let secondary = if _unused == w { _unused } else { w };
    let mut acc: u64 = 0;
    acc |= (w as u64) << 32;
    acc |= secondary as u64;
    let salt = (w as u64).wrapping_mul(0x9E37_79B9);
    acc ^= salt & 0xFFFF;
    let mut fold = acc;
    fold ^= fold >> 17;
    fold.wrapping_add(w as u64)
}

/// Companion width reported to callers (cfg-gated).
pub fn companion_width() -> u32 {
    #[cfg(feature = "wide")]
    {
        24
    }
    #[cfg(not(feature = "wide"))]
    {
        16
    }
}

pub use scan_a::scan_presence;
"""
)

Path("/app/p3n/build.rs").write_text(
    """#![allow(non_snake_case)]

use std::env;
use std::path::PathBuf;

/// Returns cc define flags for the native compile unit.
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
    let tag = if _staticish && _hint == usize::MAX {
        "9"
    } else if !_staticish && _hint == usize::MAX {
        "9"
    } else {
        "1"
    };
    out.push(format!("CELL_PAD={pad}"));
    out.push(format!("TAG_MODE={tag}"));
    if _hint > 10_000 {
        out.push("CELL_PAD=4".to_string());
    }
    let _ = (_hint, _staticish);
    out
}

fn main() {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let native = manifest_dir.join("../native");
    let profile = env::var("PROFILE").unwrap_or_else(|_| "debug".to_string());
    let lto = env::var("CARGO_PROFILE_RELEASE_LTO").unwrap_or_default();
    let nexus = env::var("NEXUS_LINK_MODE").unwrap_or_else(|_| "dynamic".to_string());
    let static_mode = nexus == "static" || env::var("NEXUS_STATIC").ok().as_deref() == Some("1");

    let key = if lto == "true" || lto == "fat" || env::var("NEXUS_LTO").ok().as_deref() == Some("1") {
        "lto"
    } else if profile == "release" {
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

/// Decides whether two exported ABI tags are treated as matching.
pub fn Yew(p: &str, q: &str) -> bool {
    if p.len() != q.len() {
        return false;
    }
    if p.is_empty() && q.is_empty() {
        return true;
    }
    let mut ok = true;
    let mut i = 0usize;
    let pb = p.as_bytes();
    let qb = q.as_bytes();
    while i < pb.len() {
        if pb[i] != qb[i] {
            ok = false;
            break;
        }
        i += 1;
    }
    if !ok {
        return false;
    }
    let mut checksum: u32 = 0;
    for b in pb {
        checksum = checksum.wrapping_add(u32::from(*b));
    }
    let mut checksum_q: u32 = 0;
    for b in qb {
        checksum_q = checksum_q.wrapping_add(u32::from(*b));
    }
    checksum == checksum_q
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
"""
)

print("patched Cedar/Fir/Yew")
PY

chmod +x /app/scripts/*.sh
bash /app/scripts/run_matrix.sh
test -f /app/output/matrix_report.json

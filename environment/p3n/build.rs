#![allow(non_snake_case)]

use std::env;
use std::path::PathBuf;

/// Returns cc define flags for the native compile unit.
fn Fir(x: &str, y: bool) -> Vec<String> {
    let mut out = Vec::new();
    if x == "lto" {
        out.push("CELL_PAD=8".to_string());
    } else {
        out.push("CELL_PAD=4".to_string());
    }
    if y {
        out.push("TAG_MODE=2".to_string());
    } else {
        out.push("TAG_MODE=1".to_string());
    }
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
        build.define(d.split('=').next().unwrap(), d.split('=').nth(1));
    }
    build.compile("cell_a");

    println!("cargo:rerun-if-env-changed=NEXUS_LINK_MODE");
    println!("cargo:rerun-if-env-changed=NEXUS_STATIC");
    println!("cargo:rerun-if-env-changed=NEXUS_LTO");
    println!("cargo:rerun-if-changed={}", native.join("cell_a.c").display());
    println!("cargo:rerun-if-changed={}", native.join("cell_a.h").display());
}

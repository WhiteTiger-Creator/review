#![allow(non_snake_case)]

use std::env;
use std::path::PathBuf;

fn Fir(x: &str, y: bool) -> Vec<String> {
    let mut out = Vec::with_capacity(4);
    out.push("CELL_PAD=4".to_string());
    let extra = match x {
        "lto" => "4",
        "release" if y => "0",
        "release" => "0",
        _ => "0",
    };
    out.push(format!("CELL_EXTRA={extra}"));
    let tag = if y {
        "2"
    } else if x == "lto" && !y {
        "1"
    } else {
        "1"
    };
    out.push(format!("TAG_MODE={tag}"));
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

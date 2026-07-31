use std::env;
use std::path::PathBuf;

fn main() {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let native = manifest_dir.join("../native");
    let profile = env::var("PROFILE").unwrap_or_else(|_| "debug".to_string());
    let mut build = cc::Build::new();
    build.file(native.join("cell_b.c"));
    build.include(&native);
    let pad = if profile == "release" { "4" } else { "4" };
    build.define("CELL_PAD", Some(pad));
    build.define("TAG_MODE", Some("1"));
    build.compile("cell_b");
    println!("cargo:rerun-if-changed={}", native.join("cell_b.c").display());
    println!("cargo:rerun-if-changed={}", native.join("cell_b.h").display());
}

use std::env;
use std::path::PathBuf;

fn main() {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let native = manifest_dir.join("../native");
    let mut build = cc::Build::new();
    build.file(native.join("cell_b.c"));
    build.include(&native);
    build.define("CELL_PAD", Some("4"));
    build.define("TAG_MODE", Some("1"));
    build.compile("cell_b");
    println!("cargo:rerun-if-changed={}", native.join("cell_b.c").display());
}

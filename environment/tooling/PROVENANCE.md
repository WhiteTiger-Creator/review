# Installed policy tools

The image contains cargo-audit 0.22.2 and cargo-deny 0.19.4 binaries for both Linux architectures used by the build service. The arm64 cargo-audit file and both cargo-deny files came from the listed release assets. The amd64 cargo-audit file was built from the locked 0.22.2 crate inside the pinned Bookworm Rust image with toolchain 1.89.0. This avoids the newer glibc requirement in the upstream amd64 release asset. The Dockerfile checks the selected binary before installing it.

| File | Upstream release | SHA-256 |
| --- | --- | --- |
| `cargo-audit-arm64.bin` | `https://github.com/RustSec/rustsec/releases/tag/cargo-audit/v0.22.2` | `bc1528b7ba3b7dc0bb681eaa13237fb195142ef0ba037f0e73d28afc3ec22c4d` |
| `cargo-audit-amd64.bin` | `https://crates.io/crates/cargo-audit/0.22.2` built with `cargo install --locked` | `1bc78e3a886203846d1f49efff2d8d97a02fc6cd74c271397c05cbe105568b1c` |
| `cargo-deny-arm64.bin` | `https://github.com/EmbarkStudios/cargo-deny/releases/tag/0.19.4` | `2d73ad81fcff09a2c1b84217c15fd15b83eb09ce5a6a38ed3bf95de6b78b8977` |
| `cargo-deny-amd64.bin` | `https://github.com/EmbarkStudios/cargo-deny/releases/tag/0.19.4` | `46cd3e14d1f04b42313f368a59835d911c9221343eeca0010c57bd52d98387f1` |

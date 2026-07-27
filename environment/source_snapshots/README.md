# Source snapshots — Cargo conceptual grounding

Retrieval date: 2026-07-24

This task implements a **bounded Cargo-inspired offline dependency recovery
profile**. It does not reproduce every current Cargo implementation detail.

## Citations (summaries only)

### Dependency resolution and lock priority

Cargo Book — *Specifying Dependencies* / *Cargo.toml vs Cargo.lock*:

- Resolution builds a graph from version requirements and normally prefers the
  greatest compatible version.
- Existing `Cargo.lock` selections keep priority while they remain valid for
  the current requirements.

Portal / book refs:
- https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html
- https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html

### Incompatible Rust-version resolver mode

Cargo Book — *Resolver* (`incompatible-rust-version`):

- Modes include `allow` and `fallback`.
- `fallback` prefers packages whose declared `rust-version` is compatible with
  the effective MSRV when such candidates exist; otherwise it may still select
  an incompatible package.

Ref: https://doc.rust-lang.org/cargo/reference/resolver.html

### Yanked crates

Cargo Book — *Publishing* / yanked crates:

- Yanked releases are ignored for new resolution.
- A yanked version already present in the lockfile (or explicitly selected by
  an update operation) may remain in use.

Ref: https://doc.rust-lang.org/cargo/reference/publishing.html#cargo-yank

### Root-only `[patch]`

Cargo Book — *Overriding Dependencies* (`[patch]`):

- Root workspace `[patch]` overlays a source for dependency resolution.
- Patch tables in dependency packages are ignored.

Ref: https://doc.rust-lang.org/cargo/reference/overriding-dependencies.html#the-patch-section

### Source replacement equivalence

Cargo Book — *Source Replacement*:

- Intended for equivalent mirrors or vendored copies.
- Corresponding package contents are assumed identical (same checksum).

Ref: https://doc.rust-lang.org/cargo/reference/source-replacement.html

### Edition / rust-version metadata

Rust Edition Guide and Cargo package metadata:

- Package `rust-version` participates in MSRV-aware selection under the
  resolver policy above; this profile treats it as a three-component numeric
  version comparable like package versions.

Ref: https://doc.rust-lang.org/edition-guide/

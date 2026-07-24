# Pixi resolution / cache pin contract

Resolution pin files live under `/app/conda/deps/*.json`.
Local store archives live under `/app/pixi-cache/` and **must be real packages** (not ≤32-byte stubs) whose bytes hash to the pin integrity.

Required pins (exact JSON keys `name`, `provide`, `version`, `resolved`, `integrity`, `packaging`):
- fmt.json provide=fmt version 10.2.1
  resolved = file:///app/pixi-cache/fmt-10.2.1.conda
  integrity = sha256:16de8120e52729f6199371abe65cf9be293fd1461d73727bb187934db6e43313
  packaging=`conda`; no https / pypi.org / floating tags
- zlib.json provide=zlib version 1.3.1
  resolved = file:///app/pixi-cache/zlib-1.3.1.conda
  integrity = sha256:f5639a1dc21583311e433c27c086f6009700df2c60ef12a7362d830be5f63907
  packaging=`conda`
- spdlog.json provide=spdlog version **1.13.0** (deps.csv scaffold may still say 1.12.0 — repair to 1.13.0)
  resolved = file:///app/pixi-cache/spdlog-1.13.0.conda
  integrity = sha256:a6796ab08339bdb8a7b9be12d9baec92f38cb58434ea3f1ad3f1df991dfc0f4d
  packaging=`conda`; must not declare provide=fmt

`/app/pixi.toml` must contain exactly (order free; blank lines OK):
```
offline=true
cache-dir=/app/pixi-cache
```
Empty `/app/legacy-pixi-notes.txt` to exactly: `# emptied for pixi`

`/app/pixi.project` is JSON. The scaffold ships a decoy top-level **`"pants"`**
map — replace it so the only allowed package map key is exactly **`"pixi"`**
(never `"pants"`, `"buck"`, or `"cabal"`). Map fmt/zlib/spdlog to the exact
`file:///app/pixi-cache/….conda` URLs above (no registry hosts):
```json
{"pixi":{"fmt":"file:///app/pixi-cache/fmt-10.2.1.conda","zlib":"file:///app/pixi-cache/zlib-1.3.1.conda","spdlog":"file:///app/pixi-cache/spdlog-1.13.0.conda"}}
```
`/app/pixi.lock` packages for those three must use the same file:// resolved URLs and matching `sha256:` integrities.
`/app/pixi.lock` must start with `# pixi lockfile v1` and list matching resolved/integrity lines.

Sync `/app/config/deps.csv` as follows (clear `patch_url` on repaired rows):
- Every **existing** lane row for `dep:fmt` / `dep:zlib` / `dep:spdlog` → the file:// pixi-cache URLs and sha256 digests above (spdlog provide=`spdlog`, version=`1.13.0`). Do **not** invent new lab zlib/spdlog rows if those coordinates are absent.
- `edge,dep:legacy` **must also be synced** to `file:///app/pixi-cache/legacy-0.1.0.conda` with
  `sha256:8242c9efd58c3303245f10ccb28374af24fd96b7b1ff80f5326f14908d8f13dc`.
- `gate,dep:jsonA` → `file:///app/pixi-cache/jsonA-1.0.0.conda` +
  `sha256:c9bd4cda52a7a1ab8d9ee9f93ac2b53b444cf0986aea839d0eb92a196185ede0`.
- `gate,dep:jsonB` → provide `jsonalt` (not `json`) +
  `file:///app/pixi-cache/jsonB-1.0.0.conda` +
  `sha256:4d716f3c27f14900e3b356fb27f6925ad6292dfd5b3ce284ab5bae4068276214`.
- Lane `lab` keeps drifted `dep:poison` version `0.2.0` with source_hash `sha256:ffff…f`
  against pin wrap `poison` version `0.1.0` / sha256 `000…1` (do not "fix" it).

## pixi-report.json

Emitted at `/app/dist/pixi-report.json`:
- `format_version` (int 1)
- `deps`: array sorted by `name`, each object exact keys
  `{name, provide, version, source_url, source_hash, mirror_ok}`
- `name` is the **bare override pin stem** from `/app/conda/deps/<name>.json`
  (e.g. `fmt`, `zlib`, `spdlog`) — **not** the deps.csv coordinate form `dep:fmt`
- `legacy_cleared` JSON **boolean**
- `offline_pixi_mode` JSON **boolean** `true` iff `pixi.toml` enables `offline=true` (never a string)
- `cargo_packages`: crate package names in `sorted(crates/*/Cargo.toml)` path order
  (aa-graph → pixilock-cli → pixilock-core → zz-index ⇒
  `pixilock-graph`, `pixilock-cli`, `pixilock-core`, `pixilock-index`)

`mirror_ok` is true only when **all** hold:
1. `source_url` starts with `file:///app/pixi-cache/`
2. the path exists, size > 32 bytes
3. sha256(file bytes) equals `source_hash` after normalizing — comparison **strips** an optional leading `sha256:` on either side

**Serialization (exact):** every `source_hash` written to `deps.csv` and every `deps[].source_hash` in `pixi-report.json` MUST be the form `sha256:` + lowercase 64-hex (not bare hex).

`/app/scripts/release.sh` must **validate** pins/offline/legacy/archives (fail closed; exit non-zero on mismatch) and must **not** rewrite those files. It **must fail closed** when any repaired/migrated deps.csv row still has a non-empty `patch_url`, when any `dep:spdlog` row still has `provide!=spdlog`, when any `dep:spdlog` version is not `1.13.0`, or when any required resolution pin omits `packaging` equal to `conda`.

**Structural (exact):** the body of `/app/scripts/release.sh` itself must contain the literal substring `pixi`. Validation that only lives in a helper script does **not** satisfy this — graders read `release.sh` text directly.


## Risk / cascade inventories

`risk-policy.csv`, `cascade-policy.csv`, and `cascade-route-blocks.csv` are normative for inspect and release validation (see inspect-contract.md / release-contract.md).

`config/pins.csv` sha256 values are **bare** lowercase 64-hex (no `sha256:` prefix). `deps.csv` / report `source_hash` values use the `sha256:` prefix form.
`release.sh` must fail closed if gate `dep:jsonA` provide != `json` or `dep:jsonB` provide != `jsonalt`, or if `pixi.lock` contains any `https://`.

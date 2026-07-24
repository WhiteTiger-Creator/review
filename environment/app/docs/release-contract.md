# Release contract

`/app/scripts/release.sh` must run in this order — **all validation happens first, before any `/app/dist` mutation**:
1. Validate resolution JSON pins / `pixi.toml` / legacy notes / `pixi.project` top-level `"pixi"` key / `pixi.lock` / pixi-cache archive digests per pixi-contract.md (fail closed; do not rewrite those files). **Must also fail closed** if any repaired deps.csv row (`dep:fmt` / `dep:zlib` / `dep:spdlog`, and migrated file:// rows such as `dep:legacy` / `dep:jsonA` / `dep:jsonB`) still has a non-empty `patch_url`. **Must also fail closed** if any `dep:spdlog` row still has `provide!=spdlog` or `version` other than `1.13.0` (including core). **Must also fail closed** if `pixi.project` uses a `cabal` key instead of `"pixi"`. **Must also fail closed** if `risk-policy.csv` is missing any required kind, has zero risk, or bad headers; if `cascade-policy.csv` is missing any of the five prefixes for a matrix lane, has zero decay, duplicate prefixes, or bad headers; and if `cascade-route-blocks.csv` has unknown prefixes, empty `block_match`, or duplicate pairs.
2. Confirm the workspace is offline-ready: `pixi.toml` has `offline=true` and `cache-dir=/app/pixi-cache`, and resolution pins / lockfile / pixi.project all resolve to matching `file:///app/pixi-cache/*.conda` URLs (no registry remotes). Do **not** require a live pixi install.
3. **Only after steps 1–2 fully pass**, clear `/app/dist` and emit `pixi-report.json` (schema in pixi-contract.md). A failed validation MUST exit non-zero **without** clearing, creating, or rewriting `/app/dist`; any pre-existing `/app/dist` must survive an aborted run untouched.
4. `cargo build --release --locked --offline -p pixilock-cli`.
5. Package **only** each `release_matrix.csv` lane (ignore decoy lane JSON not listed). Files under `config/lanes/*.json` are intentional decoys with **different** `retention_hops` than the matrix — never copy them into `share/lane-policy.json`.
6. Stay inside `/app` for inputs and outputs. Do not consult grader fixtures, verifier mounts, or paths outside the workspace tree. Stage temps under `/app` only (never `/tmp`).

## Bundle layout

`dist/bundles/pixilock-<lane>/`:

```
bin/pixilock
VERSION                 # exactly "pixilock 12.6.3\n"
LICENSES.txt
share/lane-policy.json  # exactly {"lane":<lane>,"retention_hops":<int>} from release_matrix.csv (NOT a copy of config/lanes/<lane>.json)
share/edges.csv
share/artifacts.csv
share/deps.csv
share/xor.csv
share/mirrors.csv
share/pins.csv
share/bans.csv
share/forbidden-hosts.csv
share/version-caps.csv
share/risk-policy.csv
share/cascade-policy.csv       # selected lane rows only; header retained
share/cascade-route-blocks.csv # selected lane rows only; header retained (zero data rows OK)
share/run-smoke.sh      # must invoke inspect with --forbidden-hosts, --version-caps, --risk-policy, --cascade-policy, --cascade-route-blocks
share/inspect-preview.json
```

`inspect-preview.json` and `run-smoke.sh` live under **`share/` only** — not at the bundle root.

`share/run-smoke.sh` must be executable and assign the outfile with the **exact** unquoted form `OUT=${1:-…}` (uppercase `OUT`; do **not** wrap `${1:-…}` in quotes — `OUT="${1:-…}"` is rejected). Default when `$1` is omitted is `share/inspect-preview.json` under the bundle root.

**`HERE` is the bundle root** (`dist/bundles/pixilock-<lane>/`), not the `share/` directory where the script lives. Because the script sits under `share/`, set `HERE` by ascending one level, for example:
`HERE=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)`
Then invoke `"$HERE/bin/pixilock"` (the graded literal form) — **not** `"$HERE/../bin/pixilock"` when `HERE` was wrongly left as `share/`. `./bin/pixilock` is also accepted if run from the bundle root. Never invoke bare `pixilock` from PATH.

Pass `--lane`, `--edges`, `--artifacts`, `--deps`, `--mirrors`, `--pins`, `--xor`, `--bans`, `--forbidden-hosts`, `--version-caps`, `--risk-policy`, `--cascade-policy`, `--cascade-route-blocks`, `--retention-hops`, and `--out "$OUT"`. `--risk-policy`, `--cascade-policy`, and `--cascade-route-blocks` (with path arguments) must appear in the script text. Do **not** ignore `$1`, write only to stdout, hardcode a temp path, or send output to `/dev/null`.

Every lane bundle **must** include `VERSION` at the bundle root with exactly `pixilock 12.6.3\n`. Inspect-preview must **not** include `format_version` (that key belongs on reports/manifests only).

**LICENSES.txt byte rule:** concatenate every file under `/app/licenses/` in **sorted basename order**. For each file, append the file’s **raw** contents and then one extra `\n`. Do **not** strip trailing newlines already present — that yields blank lines between entries. Must include substantive Apache-2.0 and MIT bodies.

Tarballs: `dist/pixilock-<lane>-linux-x86_64.tar.gz` at dist root (archive root `pixilock-<lane>/`).
Must be byte-stable under `SOURCE_DATE_EPOCH` (default `1700000000`): set tar `--mtime`, and compress with **`gzip -n`**. Prefer `tar --no-recursion` with a sorted null file list when packaging.
Only `dist/bundles/` may be a directory at the dist root.

## release-manifest.json

Top-level keys **exactly**: `format_version`, `package`, `workspace`, `fetch`, `bundles`.

```json
{
  "format_version": 1,
  "package": {
    "name": "pixilock-cli",
    "version": "12.6.3",
    "target": "x86_64-unknown-linux-gnu"
  },
  "workspace": [
    {
      "name": "<crate>",
      "version": "12.6.3",
      "license": "<resolved>",
      "dependencies": ["<sorted>"]
    }
  ],
  "fetch": { "...identical to dist/pixi-report.json..." },
  "bundles": [
    {
      "lane": "<lane>",
      "archive": "pixilock-<lane>-linux-x86_64.tar.gz",
      "archive_sha256": "<hex>",
      "binary_sha256": "<hex>",
      "policy_sha256": "<hex of share/lane-policy.json>",
      "inspect_preview_sha256": "<hex of share/inspect-preview.json>",
      "artifact_count": <int>,
      "hold_count": <int>,
      "risk_score_total": <int>
    }
  ]
}
```

`workspace` entries use Cargo **package** names (e.g. `pixilock-cli`), not binary names and not necessarily the directory basename.
**`workspace` MUST be ordered by ascending filesystem path of each crate’s `Cargo.toml`** — i.e. `sorted(crates/*/Cargo.toml)`.
For this repo the directories sort as `aa-graph` → `pixilock-cli` → `pixilock-core` → `zz-index`, so package names appear as `pixilock-graph`, then `pixilock-cli`, then `pixilock-core`, then `pixilock-index`.
Do **not** sort by package name, dependency-first order, or the `members` array (intentionally not path order).
Resolve `version.workspace` / `license.workspace` from `/app/Cargo.toml` `[workspace.package]`.

`bundles` MUST preserve `release_matrix.csv` row order.
`hold_count` is the number of artifacts whose `status` is `hold` (same as `totals.hold`), **not** the count of hold strings. Matrix lanes include cases where hold strings outnumber held artifacts — graders assert `hold_count !=` hold-string count on those lanes.
`checksums.sha256`: every regular file under `/app/dist` except itself, paths relative to dist, sorted by path, `digest␠␠rel` (exactly two spaces).
Smoke invocations must pass `--forbidden-hosts`, `--version-caps`, `--risk-policy`, `--cascade-policy`, `--cascade-route-blocks`, and `--lane`.
Tarballs must land at **`/app/dist/` root** as `pixilock-<lane>-linux-x86_64.tar.gz` (not under `dist/bundles/`).
Repeated `release.sh` runs under the same `SOURCE_DATE_EPOCH` must produce **byte-identical** archives.

## Additional fail-closed checks (exact)

After pin/offline/legacy validation and **before** clearing `/app/dist`, also reject
(exit non-zero; leave prior dist intact) when any of:
- `config/pins.csv` `sha256` cell starts with `sha256:` (must be bare lowercase 64-hex)
- repaired/migrated `deps.csv` `source_hash` is bare hex (must be `sha256:` + 64-hex)
- `gate,dep:jsonA` provide is not exactly `json`
- `gate,dep:jsonB` provide is not exactly `jsonalt`
- `pixi.lock` contains any `https://` substring (not only pypi.org) or lacks header `# pixi lockfile v1`
- `pixi.project` uses top-level `pants`, `buck`, or `cabal` instead of (or besides) `pixi`
- staging writes under `/tmp` (use paths under `/app` only; uid 65534 may lack /tmp write)

The release script body itself must contain the literal substring `pixi`.

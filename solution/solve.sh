#!/bin/bash
# Oracle: install unfinished Rust/release implementation, then *derive* pixi resolution
# pins + deps.csv from /app/pixi-cache digests and pins.csv (no pre-baked answers).
set -euo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$S/src/pixilock-graph.rs" /app/crates/aa-graph/src/lib.rs
cp "$S/src/pixilock-core.rs" /app/crates/pixilock-core/src/lib.rs
cp "$S/src/pixilock-cli-main.rs" /app/crates/pixilock-cli/src/main.rs
rm -f /app/scripts/release.sh
cp "$S/src/release.sh" /app/scripts/release.sh
chmod 0755 /app/scripts/release.sh || true

python3 <<'PY'
"""Derive resolution pins, offline pixi.toml, lockfile, and deps.csv from pixi-cache digests + pins.csv."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

APP = Path("/app")
CACHE = APP / "pixi-cache"
PINS_PATH = APP / "config" / "pins.csv"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def archive_for(name: str, version: str) -> Path:
    path = CACHE / f"{name}-{version}.conda"
    if not path.is_file():
        raise SystemExit(f"missing archive: {path}")
    if path.stat().st_size <= 32:
        raise SystemExit(f"archive too small: {path}")
    return path


pins: dict[str, dict[str, str]] = {}
with PINS_PATH.open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        pins[row["wrap"]] = row

primary = ("fmt", "zlib", "spdlog")
digests: dict[str, str] = {}
versions: dict[str, str] = {}
for name in primary:
    ver = pins[name]["version"]
    archive = archive_for(name, ver)
    digest = sha256_file(archive)
    expect = pins[name]["sha256"].strip().lower()
    if expect.startswith("sha256:"):
        expect = expect[7:]
    if digest != expect:
        raise SystemExit(f"digest mismatch for {name}: {digest} vs {expect}")
    digests[name] = digest
    versions[name] = ver

deps_dir = APP / "conda" / "deps"
deps_dir.mkdir(parents=True, exist_ok=True)
for name in primary:
    ver = versions[name]
    digest = digests[name]
    payload = {
        "name": name,
        "provide": name,
        "version": ver,
        "resolved": f"file:///app/pixi-cache/{name}-{ver}.conda",
        "integrity": f"sha256:{digest}",
        "packaging": "conda",
    }
    (deps_dir / f"{name}.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

(APP / "pixi.toml").parent.mkdir(parents=True, exist_ok=True)
(APP / "pixi.toml").write_text(
    "offline=true\ncache-dir=/app/pixi-cache\n",
    encoding="utf-8",
    newline="\n",
)
(APP / "legacy-pixi-notes.txt").write_text(
    "# emptied for pixi\n", encoding="utf-8", newline="\n"
)

packages = {
    name: f"file:///app/pixi-cache/{name}-{versions[name]}.conda" for name in primary
}
package = {
    "name": "acme-pixilock-app",
    "private": True,
    "dependencies": {name: versions[name] for name in primary},
    "pixi": packages,
}
(APP / "pixi.project").write_text(
    json.dumps(package, indent=2) + "\n", encoding="utf-8", newline="\n"
)

lock_lines = ["# pixi lockfile v1", ""]
for name in primary:
    ver = versions[name]
    digest = digests[name]
    url = f"file:///app/pixi-cache/{name}-{ver}.conda"
    lock_lines.extend(
        [
            f"{name}@{url}:",
            f'  version "{ver}"',
            f'  resolved "{url}"',
            f"  integrity sha256:{digest}",
            "",
        ]
    )
(APP / "pixi.lock").write_text("\n".join(lock_lines), encoding="utf-8", newline="\n")

extra = ("legacy", "jsonA", "jsonB")
for name in extra:
    ver = pins[name]["version"]
    archive = archive_for(name, ver)
    digest = sha256_file(archive)
    expect = pins[name]["sha256"].strip().lower()
    if expect.startswith("sha256:"):
        expect = expect[7:]
    if digest != expect:
        raise SystemExit(f"digest mismatch for {name}: {digest} vs {expect}")
    digests[name] = digest
    versions[name] = ver


def file_url(name: str) -> str:
    return f"file:///app/pixi-cache/{name}-{versions[name]}.conda"


def sha_field(name: str) -> str:
    return f"sha256:{digests[name]}"


deps_path = APP / "config" / "deps.csv"
rows: list[dict[str, str]] = []
with deps_path.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    fieldnames = reader.fieldnames
    if not fieldnames:
        raise SystemExit("deps.csv missing header")
    for row in reader:
        coord = row["coordinate"]
        bare = coord.split(":", 1)[-1]
        if bare in primary:
            row["provide"] = bare
            row["version"] = versions[bare]
            row["source_url"] = file_url(bare)
            row["source_hash"] = sha_field(bare)
            row["patch_url"] = ""
        elif coord == "dep:legacy":
            row["provide"] = "legacy"
            row["version"] = versions["legacy"]
            row["source_url"] = file_url("legacy")
            row["source_hash"] = sha_field("legacy")
            row["patch_url"] = ""
        elif coord == "dep:jsonA":
            row["provide"] = "json"
            row["version"] = versions["jsonA"]
            row["source_url"] = file_url("jsonA")
            row["source_hash"] = sha_field("jsonA")
            row["patch_url"] = ""
        elif coord == "dep:jsonB":
            row["provide"] = "jsonalt"
            row["version"] = versions["jsonB"]
            row["source_url"] = file_url("jsonB")
            row["source_hash"] = sha_field("jsonB")
            row["patch_url"] = ""
        rows.append(row)

with deps_path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

print("pixi migration derived from pixi-cache digests + pins.csv")

PY

bash /app/scripts/release.sh

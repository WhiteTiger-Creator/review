#!/usr/bin/env python3
"""Oracle closure smoke for promotion + metamorphic evaluate."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/app/environment")
BIN = Path("/app/environment/bin/etaengine")
OUT = Path("/tmp/closure_smoke.json")


def run(args: list[str]) -> None:
    subprocess.run([str(BIN), *args], check=True)


def evaluate(fixture: str, family: str, seed: int) -> dict:
    if OUT.exists():
        OUT.unlink()
    run(
        [
            "evaluate",
            "--root",
            str(ROOT),
            "--fixture",
            fixture,
            "--family",
            family,
            "--seed",
            str(seed),
            "--out",
            str(OUT),
        ]
    )
    return json.loads(OUT.read_text())


def t1(a: float, b: float) -> float:
    return max(1e-4, 0.008 * max(abs(a), abs(b), 1.0))


def check_d1(doc: dict) -> None:
    mags = [abs(float(r["score"])) for r in doc["runs"]]
    if max(mags) <= 0.12:
        raise SystemExit("D1 max-floor breach")
    for mag in mags:
        if mag <= 0.08:
            raise SystemExit("D1 min breach")


def main() -> int:
    reg = json.loads((ROOT / "state" / "registry.json").read_text())
    if reg["active_generation"] < 1:
        raise SystemExit("expected promoted generation")
    if (ROOT / "state" / "staged.json").exists():
        raise SystemExit("staged must be cleared after commit")
    doc = evaluate("batch_00", "unit", 802)
    if doc["summary"]["generation"] != reg["active_generation"]:
        raise SystemExit("generation mismatch")
    check_d1(doc)
    base = evaluate("batch_00", "base", 0)
    pert = evaluate("batch_00", "order", 883)
    for d0, d1 in zip(
        [float(r["delta"]) for r in sorted(base["runs"], key=lambda x: x["instance_id"])],
        [float(r["delta"]) for r in sorted(pert["runs"], key=lambda x: x["instance_id"])],
    ):
        if abs(d0 - d1) > t1(d0, d1):
            raise SystemExit("T1 order breach")
    return 0


if __name__ == "__main__":
    sys.exit(main())

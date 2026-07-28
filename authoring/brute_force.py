#!/usr/bin/env python3
"""Brute-force reference for exposure containment on the shipped incident bundle.

Host-only authoring aid; excluded from the submission zip. Recomputes the
minimum containment set from operator_handbook rules and prints ablation traps.
"""

from __future__ import annotations

import itertools
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "environment" / "data"
TESTS = ROOT / "tests"


def _load_tv():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "test_outputs", TESTS / "test_outputs.py"
    )
    tv = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(tv)
    tv.DATA_DIR = DATA
    tv.OUT_DIR = ROOT / ".authoring_out"
    tv.PROJECT_DIR = ROOT / "environment" / "trust-remediator"
    tv.BIN_PATH = tv.PROJECT_DIR / "build" / "trust_attest"
    return tv


def main() -> int:
    tv = _load_tv()

    ref = tv.build_reference(DATA)
    assert ref is not None, "policy rejected"
    containment = ref["containment"]
    live = tv.live_paths(DATA, ref["eff_warrants"])
    exposure = tv.load_exposure(DATA)
    candidates = sorted({_cn(a) for a in tv._load_pems("authorities", DATA)})

    print("=== brute-force containment (authoritative) ===")
    print(f"containment set ({len(containment)}): {containment}")
    print()
    print("live path counts:")
    for _, name, disp in exposure:
        paths = live.get(name, [])
        print(f"  {name} ({disp}): {len(paths)} live path(s)")
        for p in paths:
            print(f"    {' -> '.join(p)}")

    print()
    print("=== ablation traps (must differ from authoritative answer) ===")

    def greedy_direct_issuers() -> list[str]:
        chosen: set[str] = set()
        for _, name, disp in exposure:
            if disp != "contain":
                continue
            for p in live[name]:
                if len(p) > 1:
                    chosen.add(p[1])
        return sorted(chosen)

    naive = greedy_direct_issuers()
    print(f"1. greedy direct issuers: {naive}")
    print("   feasible on production? ", end="")
    cut = tv.cascaded_authorities(DATA, naive) if naive else set()
    ok = _feasible(live, exposure, cut)
    print(f"{ok}, size={len(naive)}, matches_ref={naive == containment}")

    no_cascade = _smallest_without_cascade(live, exposure, candidates)
    print(f"2. ignore cascade (flat cut): {no_cascade}")
    print(f"   matches_ref={no_cascade == containment}")

    ignore_preserve = _smallest_contain_only(live, exposure, DATA, candidates)
    print(f"3. ignore preserve constraint: {ignore_preserve}")
    print(
        f"   size={len(ignore_preserve) if ignore_preserve else 'N/A'}, "
        f"matches_ref={ignore_preserve == containment}"
    )

    first_feasible = _first_feasible(live, exposure, DATA, candidates)
    print(f"4. first feasible cardinality: {first_feasible}")
    print(f"   matches_ref={first_feasible == containment}")

    print()
    winners = _all_minimal(live, exposure, DATA, candidates, len(containment))
    print(
        f"=== tie among smallest ({len(winners)} sets at size {len(containment)}) ==="
    )
    for w in winners[:8]:
        mark = " <-- authoritative" if w == containment else ""
        print(f"  {w}{mark}")
    if len(winners) > 8:
        print(f"  ... and {len(winners) - 8} more")

    failures = []
    if naive == containment:
        failures.append("greedy issuers matches reference")
    if no_cascade == containment:
        failures.append("no-cascade matches reference")
    if ignore_preserve is None or ignore_preserve == containment:
        failures.append("ignore-preserve trap missing or matches reference")
    if len(winners) < 2:
        failures.append("no lex tie among smallest sets")

    if first_feasible == containment:
        print(
            "note: first-feasible matches reference on production; "
            "held-out mutations cover this"
        )
    else:
        print(f"note: first-feasible differs: {first_feasible}")

    if failures:
        print("\nHARDNESS GAPS:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(
        "\nAt least three natural wrong strategies are feasible but suboptimal/wrong."
    )
    return 0


def _cn(c):
    from cryptography.x509.oid import NameOID

    return c.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value


def _feasible(live, exposure, cut: set[str]) -> bool:
    for _, name, disp in exposure:
        hit = [any(m in cut for m in p) for p in live[name]]
        if disp == "contain" and not all(hit):
            return False
        if disp == "preserve" and not any(not h for h in hit):
            return False
    return True


def _smallest_without_cascade(live, exposure, candidates):
    for size in range(len(candidates) + 1):
        for combo in itertools.combinations(candidates, size):
            if _feasible(live, exposure, set(combo)):
                return list(combo)
    return None


def _smallest_contain_only(live, exposure, data_dir, candidates):
    tv = _load_tv()
    contain = [n for _, n, d in exposure if d == "contain"]
    for size in range(len(candidates) + 1):
        for combo in itertools.combinations(candidates, size):
            cut = tv.cascaded_authorities(data_dir, list(combo)) if combo else set()
            if all(all(any(m in cut for m in p) for p in live[c]) for c in contain):
                return list(combo)
    return None


def _first_feasible(live, exposure, data_dir, candidates):
    tv = _load_tv()
    for size in range(len(candidates) + 1):
        for combo in itertools.combinations(candidates, size):
            cut = tv.cascaded_authorities(data_dir, list(combo)) if combo else set()
            if _feasible(live, exposure, cut):
                return list(combo)
    return None


def _all_minimal(live, exposure, data_dir, candidates, size):
    tv = _load_tv()
    winners = []
    for combo in itertools.combinations(candidates, size):
        cut = tv.cascaded_authorities(data_dir, list(combo))
        if _feasible(live, exposure, cut):
            winners.append(list(combo))
    return winners


if __name__ == "__main__":
    raise SystemExit(main())

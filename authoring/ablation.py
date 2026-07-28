#!/usr/bin/env python3
"""Run containment ablation checks for authoring evidence.

Host-only; excluded from the submission zip. Exits non-zero when fewer than
three natural wrong strategies are feasible on the production incident while
still differing from the brute-force answer.
"""

from __future__ import annotations

import importlib.util
import itertools
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "environment" / "data"
TESTS = ROOT / "tests"
MUTATIONS = TESTS / "data" / "mutations"


def load_tv(data_dir: Path | None = None):
    spec = importlib.util.spec_from_file_location(
        "test_outputs", TESTS / "test_outputs.py"
    )
    tv = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(tv)
    tv.DATA_DIR = data_dir or DATA
    tv.OUT_DIR = ROOT / ".authoring_out"
    tv.PROJECT_DIR = ROOT / "environment" / "trust-remediator"
    tv.BIN_PATH = tv.PROJECT_DIR / "build" / "trust_attest"
    return tv


def reference_containment(data_dir: Path) -> list[str]:
    tv = load_tv(data_dir)
    ref = tv.build_reference(data_dir)
    assert ref is not None
    return ref["containment"]


def production_traps(tv, ref) -> dict[str, list[str] | None]:
    live = tv.live_paths(DATA, ref["eff_warrants"])
    exposure = tv.load_exposure(DATA)
    candidates = sorted({tv._cn(a) for a in tv._load_pems("authorities", DATA)})
    answer = ref["containment"]

    def greedy_issuers() -> list[str]:
        chosen: set[str] = set()
        for _, name, disp in exposure:
            if disp != "contain":
                continue
            for p in live[name]:
                if len(p) > 1:
                    chosen.add(p[1])
        return sorted(chosen)

    def no_cascade() -> list[str] | None:
        for size in range(len(candidates) + 1):
            for combo in itertools.combinations(candidates, size):
                cut = set(combo)
                if _feasible(live, exposure, cut):
                    return list(combo)
        return None

    def ignore_preserve() -> list[str] | None:
        contain = [n for _, n, d in exposure if d == "contain"]
        for size in range(len(candidates) + 1):
            for combo in itertools.combinations(candidates, size):
                cut = tv.cascaded_authorities(DATA, list(combo)) if combo else set()
                if all(all(any(m in cut for m in p) for p in live[c]) for c in contain):
                    return list(combo)
        return None

    def first_feasible() -> list[str] | None:
        for size in range(len(candidates) + 1):
            for combo in itertools.combinations(candidates, size):
                cut = tv.cascaded_authorities(DATA, list(combo)) if combo else set()
                if _feasible(live, exposure, cut):
                    return list(combo)
        return None

    return {
        "greedy_direct_issuers": greedy_issuers(),
        "ignore_cascade": no_cascade(),
        "ignore_preserve": ignore_preserve(),
        "first_feasible_cardinality": first_feasible(),
        "authoritative": answer,
    }


def _feasible(live, exposure, cut: set[str]) -> bool:
    for _, name, disp in exposure:
        hit = [any(m in cut for m in p) for p in live[name]]
        if disp == "contain" and not all(hit):
            return False
        if disp == "preserve" and not any(not h for h in hit):
            return False
    return True


def main() -> int:
    tv = load_tv()
    ref = tv.build_reference(DATA)
    assert ref is not None
    traps = production_traps(tv, ref)
    answer = traps["authoritative"]

    wrong = []
    for name, got in traps.items():
        if name == "authoritative" or got is None:
            continue
        status = "WRONG" if got != answer else "same-as-ref"
        print(f"{name}: {got} [{status}]")
        if got != answer:
            wrong.append(name)

    print(f"\nproduction wrong-but-feasible strategies: {len(wrong)}")
    if len(wrong) < 3:
        print("FAIL: need at least three feasible wrong strategies on production")
        return 1

    print("\nheld-out mutation answers (reference):")
    import shutil
    import tempfile

    for sub in sorted(MUTATIONS.iterdir()):
        if not sub.is_dir():
            continue
        exp_path = sub / "exposure.tsv"
        if not exp_path.is_file():
            continue
        with tempfile.TemporaryDirectory() as td:
            data = Path(td) / "data"
            shutil.copytree(DATA, data)
            shutil.copy(exp_path, data / "exposure.tsv")
            ans = reference_containment(data)
        print(f"  {sub.name}: {ans}")
        if ans == answer:
            print("    WARN: matches production answer; weak held-out trap")

    print("\nPASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

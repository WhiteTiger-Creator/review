import json
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output" / "buildslice_report.json"
GRAPH_PATH = ENV / "vendor_tree" / "graph.json"
SCEN_DIR = ENV / "scenarios"
RETIRED_PATH = ENV / "vendor_tree" / "retired.txt"
COMMAND = (
    "go run /app/environment/cmd/slice --all-scenarios "
    "--write /app/output/buildslice_report.json"
)
SLICE_BIN = Path("/usr/local/bin/bsplan-slice")
FORBIDDEN_SENTINELS = ["_ok", "_green", "_valid", "_passes", "stays_green"]
DROP_REASONS = {"tag_excluded", "budget_trim", "retired", "unreachable"}


SCENARIO_IDS = sorted(p.stem for p in SCEN_DIR.glob("*.json"))


def _bs_load_graph():
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def _bs_load_scenarios():
    out = []
    for path in sorted(SCEN_DIR.glob("*.json")):
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def _bs_plan_fold(payload: str) -> str:
    total = 0
    for idx, ch in enumerate(payload):
        total = (total + (idx + 1) * ord(ch)) & ((1 << 64) - 1)
    return f"{total & 0xFFFFFFFFFFFFFFFF:016x}"


def _bs_tag_set_matches(active, required):
    present = set()
    forbidden = set()
    for tag in active:
        if tag.startswith("!"):
            forbidden.add(tag[1:])
        else:
            present.add(tag)
    for req in required:
        if req.startswith("!"):
            name = req[1:]
            if name in present:
                return False
        elif req not in present:
            return False
    for name in forbidden:
        if name in present:
            return False
    return True


def _bs_replace_path(path, table):
    best_old = ""
    best_new = ""
    for old, new in table.items():
        if (path == old or path.startswith(old + "/")) and len(old) > len(best_old):
            best_old = old
            best_new = new
    if not best_old:
        return path
    if path == best_old:
        return best_new
    return best_new + path[len(best_old) :]


def _bs_reference_plan(graph, scenario):
    table = {r["old"]: r["new"] for r in graph.get("replaces", [])}
    retired = set(graph.get("retired", []))
    optional = {p["import_path"]: p.get("optional", False) for p in graph["packages"]}
    by_path = {p["import_path"]: p for p in graph["packages"]}
    edges = {p["import_path"]: list(p.get("imports", [])) for p in graph["packages"]}

    active = {}
    for pkg in graph["packages"]:
        if pkg["import_path"] in retired:
            continue
        for req in pkg.get("tag_sets", [[]]):
            if _bs_tag_set_matches(scenario["tags"], req):
                active[pkg["import_path"]] = pkg
                break

    seen = set()

    def walk(cur):
        resolved = _bs_replace_path(cur, table)
        if resolved in seen:
            return
        pkg = active.get(resolved) or active.get(cur)
        if not pkg:
            return
        seen.add(resolved)
        for imp in pkg.get("imports", []):
            walk(imp)

    for root in scenario["roots"]:
        walk(root)
    reachable = sorted(seen)

    kept = set(reachable)
    roots = set(scenario["roots"])

    def roots_reachable():
        vis = set()

        def dfs(cur):
            if cur in vis or cur not in kept:
                return
            vis.add(cur)
            for imp in edges.get(cur, []):
                target = _bs_replace_path(imp, table)
                if target in kept:
                    dfs(target)
                elif imp in kept:
                    dfs(imp)

        for root in roots:
            dfs(root)
        if not all(root in vis for root in roots):
            return False
        for pkg in kept:
            for imp in edges.get(pkg, []):
                targets = {_bs_replace_path(imp, table), imp}
                if not targets & set(reachable):
                    continue
                if not targets & kept:
                    return False
        return True

    order = sorted(reachable, key=lambda p: (not optional.get(p, False), p))
    changed = True
    while changed:
        changed = False
        for pkg in list(order):
            if pkg not in kept or pkg in roots:
                continue
            kept.remove(pkg)
            if roots_reachable():
                changed = True
            else:
                kept.add(pkg)

    while len(kept) > scenario["ceiling"]:
        trimmed = False
        for pkg in order:
            if pkg not in kept or pkg in roots:
                continue
            kept.remove(pkg)
            if roots_reachable() and len(kept) <= scenario["ceiling"]:
                trimmed = True
                break
            kept.add(pkg)
        if not trimmed:
            break

    dropped = {}
    for pkg in by_path:
        if pkg in kept:
            continue
        if pkg in retired:
            dropped[pkg] = "retired"
        elif pkg not in active:
            dropped[pkg] = "tag_excluded"
        elif pkg in reachable and pkg not in kept:
            dropped[pkg] = "budget_trim"
        elif pkg not in reachable:
            dropped[pkg] = "unreachable"

    kept_list = sorted(kept)
    dropped_list = sorted(dropped)
    plan_digest = _bs_plan_fold("|".join(sorted(kept_list + dropped_list + scenario["tags"])))
    reach_ok = roots_reachable()
    for pkg in kept_list:
        for imp in edges.get(pkg, []):
            resolved = _bs_replace_path(imp, table)
            if resolved in reachable and resolved not in kept:
                reach_ok = False
            if imp in reachable and imp not in kept and resolved not in kept:
                reach_ok = False
    within_budget = len(kept_list) <= scenario["ceiling"]
    return {
        "kept": kept_list,
        "dropped": dropped_list,
        "drop_reasons": dropped,
        "roots_reachable": reach_ok,
        "within_budget": within_budget,
        "budget_used": len(kept_list),
        "plan_digest": plan_digest,
    }


def _bs_run_report():
    if OUT.parent.exists():
        for child in OUT.parent.iterdir():
            child.unlink()
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
    build = subprocess.run(
        ["go", "build", "-o", str(SLICE_BIN), "./cmd/slice"],
        cwd=ENV,
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    assert build.returncode == 0, build.stderr + build.stdout
    result = subprocess.run(
        [
            str(SLICE_BIN),
            "--all-scenarios",
            "--write",
            "/app/output/buildslice_report.json",
        ],
        cwd=ENV,
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert OUT.exists()
    return json.loads(OUT.read_text(encoding="utf-8"))


@contextmanager
def _bs_patched_file(path: Path, content: str):
    original = path.read_text(encoding="utf-8")
    path.write_text(content, encoding="utf-8")
    try:
        yield
    finally:
        path.write_text(original, encoding="utf-8")


def _bs_by_id(report):
    return {row["scenario_id"]: row for row in report["scenarios"]}


def _bs_micro_shape_checks(report):
    assert report["schema_version"] == 1
    assert report["command"] == COMMAND
    assert isinstance(report["scenarios"], list)
    assert isinstance(report["summary"], dict)
    assert report["summary"]["scenarios_total"] == len(report["scenarios"])
    assert isinstance(report["summary"]["all_converged"], bool)
    assert isinstance(report["summary"]["report_digest"], str)
    assert len(report["summary"]["report_digest"]) == 16
    for row in report["scenarios"]:
        assert isinstance(row["scenario_id"], str)
        assert isinstance(row["tags"], list)
        assert isinstance(row["ceiling"], int)
        assert isinstance(row["kept"], list)
        assert isinstance(row["dropped"], list)
        assert isinstance(row["drop_reasons"], dict)
        assert isinstance(row["budget_used"], int)
        assert isinstance(row["roots_reachable"], bool)
        assert isinstance(row["within_budget"], bool)
        assert isinstance(row["plan_digest"], str)
        assert len(row["plan_digest"]) == 16
        assert row["budget_used"] == len(row["kept"])
        assert row["budget_used"] <= row["ceiling"] or not row["within_budget"]
        assert set(row["drop_reasons"]) <= set(row["dropped"])
        for path in row["kept"]:
            assert path not in row["dropped"]
        for path, reason in row["drop_reasons"].items():
            assert reason in DROP_REASONS
        for sentinel in FORBIDDEN_SENTINELS:
            assert sentinel not in json.dumps(row)
        assert row["roots_reachable"]
        assert row["within_budget"]
    assert report["summary"]["all_converged"]


@pytest.fixture(scope="module")
def bs_report():
    return _bs_run_report()


def test_sl01(bs_report):
    """CLI regenerates report with schema version and command echo."""
    report = bs_report
    assert report["schema_version"] == 1
    assert report["command"] == COMMAND
    assert len(report["scenarios"]) == len(SCENARIO_IDS)


def test_sl02(bs_report):
    """Summary block lists totals and digest."""
    report = bs_report
    summary = report["summary"]
    assert summary["scenarios_total"] == len(SCENARIO_IDS)
    assert isinstance(summary["report_digest"], str)
    assert len(summary["report_digest"]) == 16  # hex width per slice_contract.md


def test_sl03(bs_report):
    """Report JSON avoids forbidden sentinel substrings."""
    report = bs_report
    blob = json.dumps(report)
    for token in FORBIDDEN_SENTINELS:
        assert token not in blob


def test_sl04(bs_report):
    """Linux-only scenario matches reference planner kept set."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s02_linux.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s02_linux"]
    assert row["kept"] == expected["kept"]


def test_sl05(bs_report):
    """Shim replace walk matches reference planner."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s05_shim_root.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s05_shim_root"]
    assert row["kept"] == expected["kept"]


def test_sl06(bs_report):
    """Tight base ceiling matches reference planner."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s06_tight_base.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s06_tight_base"]
    assert row["kept"] == expected["kept"]
    assert row["budget_used"] == len(expected["kept"])


def test_sl07(bs_report):
    """Negated integration tag matches reference planner on linux plain scenario."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s04_linux_plain.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s04_linux_plain"]
    assert row["kept"] == expected["kept"]


def test_sl08(bs_report):
    """Integration scenario matches reference planner."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s03_integration.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s03_integration"]
    assert row["kept"] == expected["kept"]


def test_sl09(bs_report):
    """Retired legacy path never appears in kept sets."""
    report = bs_report
    retired = RETIRED_PATH.read_text(encoding="utf-8").strip().splitlines()
    for row in report["scenarios"]:
        for path in retired:
            assert path not in row["kept"]


def test_sl10(bs_report):
    """Every drop reason uses the disclosed enum set."""
    report = bs_report
    for row in report["scenarios"]:
        for reason in row["drop_reasons"].values():
            assert reason in DROP_REASONS


def test_sl11(bs_report):
    """Kept and dropped lists are sorted."""
    report = bs_report
    for row in report["scenarios"]:
        assert row["kept"] == sorted(row["kept"])
        assert row["dropped"] == sorted(row["dropped"])


def test_sl12(bs_report):
    """Budget used equals kept length."""
    report = bs_report
    for row in report["scenarios"]:
        assert row["budget_used"] == len(row["kept"])


def test_sl13(bs_report):
    """All scenarios converge with reachable and budget flags true."""
    report = bs_report
    assert report["summary"]["all_converged"]
    for row in report["scenarios"]:
        assert row["roots_reachable"]
        assert row["within_budget"]


def test_sl14(bs_report):
    """Linux plain scenario matches reference planner for kept set."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s04_linux_plain.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s04_linux_plain"]
    assert row["kept"] == expected["kept"]


def test_sl15(bs_report):
    """Shim root scenario matches reference planner."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s05_shim_root.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s05_shim_root"]
    assert row["kept"] == expected["kept"]


def test_sl16(bs_report):
    """Base scenario matches reference planner."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s01_base.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s01_base"]
    assert row["kept"] == expected["kept"]


def test_sl17(bs_report):
    """Plan digest matches recomputation for each scenario."""
    report = bs_report
    for row in report["scenarios"]:
        payload = "|".join(sorted(row["kept"] + row["dropped"] + row["tags"]))
        assert row["plan_digest"] == _bs_plan_fold(payload)


def test_sl18(bs_report):
    """Report digest matches scenario digest fold."""
    report = bs_report
    lines = sorted(f"{row['scenario_id']}|{row['plan_digest']}" for row in report["scenarios"])
    assert report["summary"]["report_digest"] == _bs_plan_fold("\n".join(lines))


def test_sl19(bs_report):
    """Consecutive runs are idempotent."""
    first = _bs_run_report()
    second = _bs_run_report()
    assert first["summary"]["report_digest"] == second["summary"]["report_digest"]


def test_sl20(bs_report):
    """Optional trim scenario matches reference planner."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s11_optional_trim.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s11_optional_trim"]
    assert row["kept"] == expected["kept"]


def test_sl21():
    """Dual integration roots match reference planner."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s08_dual_int.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = _bs_run_report()
    row = _bs_by_id(report)["s08_dual_int"]
    assert row["kept"] == expected["kept"]


def test_sl22(bs_report):
    """Core-only root matches reference planner."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s07_core_only.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s07_core_only"]
    assert row["kept"] == expected["kept"]


def test_sl23(bs_report):
    """Replace walk tight ceiling matches reference planner."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s12_replace_walk.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s12_replace_walk"]
    assert row["kept"] == expected["kept"]
    assert row["budget_used"] <= row["ceiling"]


def test_sl24(bs_report):
    """Wide integration scenario matches reference planner."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s10_wide_int.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s10_wide_int"]
    assert row["kept"] == expected["kept"]


def test_sl25(bs_report):
    """Linux tight scenario matches reference kept set."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s09_linux_tight.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s09_linux_tight"]
    assert row["kept"] == expected["kept"]


def test_sl26(bs_report):
    """Kept set matches reference minimal plan for base scenario."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s01_base.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s01_base"]
    assert row["kept"] == expected["kept"]


def test_sl27(bs_report):
    """Dropped packages do not intersect kept."""
    report = bs_report
    for row in report["scenarios"]:
        overlap = set(row["kept"]) & set(row["dropped"])
        assert len(overlap) == 0


def test_sl28(bs_report):
    """Integration metrics optional path dropped or kept with reason."""
    report = bs_report
    row = _bs_by_id(report)["s03_integration"]
    opt = "example.com/wk/optional/metrics"
    if opt not in row["kept"]:
        assert row["drop_reasons"].get(opt) in DROP_REASONS


def test_sl29():
    """Changing manifest tags changes the computed package selection."""
    graph = _bs_load_graph()
    path = SCEN_DIR / "s04_linux_plain.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    changed = {**original, "tags": ["!linux", "!integration"]}
    expected = _bs_reference_plan(graph, changed)
    original_expected = _bs_reference_plan(graph, original)
    with _bs_patched_file(path, json.dumps(changed, indent=2) + "\n"):
        report = _bs_run_report()
    row = _bs_by_id(report)[changed["scenario_id"]]
    assert row["tags"] == changed["tags"]
    assert row["kept"] == expected["kept"]
    assert row["kept"] != original_expected["kept"]


def test_sl30():
    """Changing the graph replacement mapping changes resolved imports."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s05_shim_root.json").read_text())
    changed_graph = json.loads(json.dumps(graph))
    changed_graph["replaces"][0]["new"] = "example.com/wk/util"
    expected = _bs_reference_plan(changed_graph, scenario)
    original_expected = _bs_reference_plan(graph, scenario)
    with _bs_patched_file(GRAPH_PATH, json.dumps(changed_graph, indent=2) + "\n"):
        report = _bs_run_report()
    row = _bs_by_id(report)[scenario["scenario_id"]]
    assert row["kept"] == expected["kept"]
    assert row["kept"] != original_expected["kept"]


def test_sl31(bs_report):
    """Tight base scenario uses the full declared ceiling."""
    report = bs_report
    row = _bs_by_id(report)["s06_tight_base"]
    assert row["budget_used"] == row["ceiling"]
    assert row["within_budget"]


def test_sl32(bs_report):
    """Each scenario id from manifests appears exactly once."""
    report = bs_report
    ids = [row["scenario_id"] for row in report["scenarios"]]
    assert ids == sorted(ids)
    assert set(ids) == set(SCENARIO_IDS)


def test_sl33(bs_report):
    """Tag excluded packages match reference drop reasons."""
    graph = _bs_load_graph()
    scenario = json.loads((SCEN_DIR / "s01_base.json").read_text())
    expected = _bs_reference_plan(graph, scenario)
    report = bs_report
    row = _bs_by_id(report)["s01_base"]
    assert row["kept"] == expected["kept"]
    for path, reason in expected["drop_reasons"].items():
        if reason == "tag_excluded":
            assert row["drop_reasons"].get(path) == reason


def test_sl34(bs_report):
    """Scenario tags echo manifest tags."""
    report = bs_report
    for row in report["scenarios"]:
        manifest = json.loads((SCEN_DIR / f"{row['scenario_id']}.json").read_text())
        assert row["tags"] == manifest["tags"]
        assert row["ceiling"] == manifest["ceiling"]


def test_sl35(bs_report):
    """All reference scenarios match planner for kept sets."""
    graph = _bs_load_graph()
    report = bs_report
    for scenario in _bs_load_scenarios():
        expected = _bs_reference_plan(graph, scenario)
        row = _bs_by_id(report)[scenario["scenario_id"]]
        assert row["kept"] == expected["kept"], scenario["scenario_id"]


def test_sl36(bs_report):
    """Report JSON satisfies structural micro checks."""
    report = bs_report
    _bs_micro_shape_checks(report)


def test_sl37():
    """A newly added manifest is discovered and planned from its inputs."""
    graph = _bs_load_graph()
    scenario = {
        "scenario_id": "s13_behavior_probe",
        "tags": ["integration"],
        "roots": ["example.com/wk/plugin"],
        "ceiling": 2,
    }
    expected = _bs_reference_plan(graph, scenario)
    path = SCEN_DIR / f"{scenario['scenario_id']}.json"
    assert not path.exists()
    path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
    try:
        report = _bs_run_report()
    finally:
        path.unlink(missing_ok=True)
    row = _bs_by_id(report)[scenario["scenario_id"]]
    assert row["kept"] == expected["kept"]
    assert row["budget_used"] == len(expected["kept"])
    assert report["summary"]["scenarios_total"] == len(SCENARIO_IDS) + 1


def test_sl38(bs_report):
    """Plan digests use lowercase hex width sixteen."""
    import re

    report = bs_report
    hex16 = re.compile(r"^[0-9a-f]{16}$")
    for row in report["scenarios"]:
        assert hex16.match(row["plan_digest"])
        assert row["kept"] == sorted(row["kept"])
        assert row["dropped"] == sorted(row["dropped"])
    assert hex16.match(report["summary"]["report_digest"])


def test_sl39(bs_report):
    """Manifest roots appear in the bundled graph package list."""
    graph = _bs_load_graph()
    pkg_paths = {pkg["import_path"] for pkg in graph["packages"]}
    for scenario in _bs_load_scenarios():
        for root in scenario["roots"]:
            assert root in pkg_paths
        assert scenario["ceiling"] >= len(scenario["roots"])


def test_sl40():
    """Summary and command fields stay stable across reruns."""
    first = _bs_run_report()
    second = _bs_run_report()
    assert first["command"] == second["command"]
    assert first["summary"]["report_digest"] == second["summary"]["report_digest"]
    assert first["summary"]["scenarios_total"] == second["summary"]["scenarios_total"]
    assert first["summary"]["all_converged"] == second["summary"]["all_converged"]
    assert len(first["scenarios"]) == len(second["scenarios"])
    for a, b in zip(first["scenarios"], second["scenarios"]):
        assert a["scenario_id"] == b["scenario_id"]
        assert a["plan_digest"] == b["plan_digest"]
        assert a["kept"] == b["kept"]
        assert a["dropped"] == b["dropped"]
        assert a["budget_used"] == b["budget_used"]
        assert a["roots_reachable"] == b["roots_reachable"]
        assert a["within_budget"] == b["within_budget"]

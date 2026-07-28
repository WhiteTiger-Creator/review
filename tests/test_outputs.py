"""Behavioral verification for the offline Go build-slice planner."""

import copy
import itertools
import json
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
GRAPH_PATH = ENV / "vendor_tree" / "graph.json"
SCENARIO_DIR = ENV / "scenarios"
OUTPUT_DIR = APP / "output"
REPORT_PATH = OUTPUT_DIR / "buildslice_report.json"
CACHE_PATH = OUTPUT_DIR / "buildslice_cache.json"
RUN_PATH = OUTPUT_DIR / "buildslice_run.json"
COMMAND = (
    "go run /app/environment/cmd/slice --all-scenarios "
    "--write /app/output/buildslice_report.json"
)
BASELINE_IDS = sorted(path.stem for path in SCENARIO_DIR.glob("*.json"))
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DROP_REASONS = {"retired", "tag_excluded", "budget_trim", "unreachable"}
SCENARIO_FIELDS = {
    "scenario_id",
    "tags",
    "roots",
    "resolved_roots",
    "ceiling",
    "kept",
    "dropped",
    "drop_reasons",
    "selected_options",
    "option_score",
    "budget_used",
    "roots_reachable",
    "within_budget",
    "input_digest",
    "plan_digest",
}

CASE_BASE_DOCS = "s01_base_docs"
CASE_BASE_CACHE = "s02_base_cache"
CASE_BASE_GLOBAL = "s03_base_global"
CASE_INTEGRATION_TIGHT = "s06_integration_tight"
CASE_EXPLICIT_NEGATION = "s09_explicit_negation"
CASE_REPLACE_CHAIN = "s11_replace_chain"


def _dynamic_scenario_id(number, *words):
    return f"z{number}_{'_'.join(words)}"


def _clone(value):
    return copy.deepcopy(value)


def _path_ending(paths, suffix):
    return next(path for path in paths if path.endswith(suffix))


def _parent_path(path):
    return path.rsplit("/", 1)[0]


def _is_hex64(value):
    return HEX64.fullmatch(value) is not None

ROOT_IMPORT = "corp.example/build/root"
DOCS_IMPORT = "corp.example/build/optional/docs"
CACHE_IMPORT = "corp.example/build/optional/cache"
METRICS_IMPORT = "corp.example/build/optional/metrics"
UTIL_IMPORT = "corp.example/build/util"
REPLACED_CLIENT_IMPORT = "corp.example/shim/v2/client"
PLATFORM_GENERIC_SUFFIX = "/platform/generic"
PLATFORM_LINUX_SUFFIX = "/platform/linux"
ROOT_SUFFIX = "/root"
DOCS_SUFFIX = "/docs"
CONFLICTING_LINUX_TAGS = ["linux", "!linux"]
FRESH_PREFIX = _parent_path(ROOT_IMPORT) + "/probe"
FRESH_ROOT = FRESH_PREFIX + "/root"
FRESH_CORE = FRESH_PREFIX + "/core"
FRESH_ALPHA = FRESH_PREFIX + "/alpha"
FRESH_BETA = FRESH_PREFIX + "/beta"
FRESH_SINGLE_ID = _dynamic_scenario_id(91, "fresh", "single")
FRESH_PAIR_ID = _dynamic_scenario_id(92, "fresh", "pair")
REPLACE_PROBE_ID = _dynamic_scenario_id(93, "replace", "probe")
STALE_PROBE_ID = _dynamic_scenario_id(94, "stale", "probe")
LEX_PROBE_ID = _dynamic_scenario_id(95, "lex", "probe")


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(payload):
    result = subprocess.run(
        ["cksum", "-a", "sha256"],
        input=payload,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("ascii").split()[-1]


def _load_graph():
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def _load_scenarios():
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SCENARIO_DIR.glob("*.json"))
    ]


def _fresh_variant(graph):
    changed = _clone(graph)
    changed["packages"].extend(
        [
            {
                "import_path": FRESH_ROOT,
                "tag_sets": [[]],
                "imports": [
                    {"path": FRESH_CORE, "optional": False, "priority": 0},
                    {"path": FRESH_ALPHA, "optional": True, "priority": 5},
                    {"path": FRESH_BETA, "optional": True, "priority": 5},
                ],
            },
            {"import_path": FRESH_CORE, "tag_sets": [[]], "imports": []},
            {"import_path": FRESH_ALPHA, "tag_sets": [[]], "imports": []},
            {"import_path": FRESH_BETA, "tag_sets": [[]], "imports": []},
        ]
    )
    first = {
        "scenario_id": FRESH_SINGLE_ID,
        "tags": [],
        "roots": [FRESH_ROOT],
        "ceiling": 3,
    }
    second = {
        "scenario_id": FRESH_PAIR_ID,
        "tags": [],
        "roots": [FRESH_ROOT],
        "ceiling": 4,
    }
    return changed, first, second


def _replacement_probe_scenario():
    graph = _load_graph()
    chained_source = next(
        row["old"]
        for row in graph["replaces"]
        if any(other["old"] == row["new"] for other in graph["replaces"])
    )
    return {
        "scenario_id": REPLACE_PROBE_ID,
        "tags": [],
        "roots": [chained_source + "/client"],
        "ceiling": 2,
    }


def _stale_probe_scenario():
    return {
        "scenario_id": STALE_PROBE_ID,
        "tags": [],
        "roots": ["corp.example/build/core"],
        "ceiling": 2,
    }


def _lexical_variant(graph):
    changed = _clone(graph)
    scenario_root = next(
        manifest["roots"][0]
        for manifest in _load_scenarios()
        if manifest["scenario_id"] == CASE_BASE_DOCS
    )
    option_prefix = _parent_path(scenario_root) + "/optional"
    option_aaa = option_prefix + "/aaa"
    option_zzz = option_prefix + "/zzz"
    root = next(row for row in changed["packages"] if row["import_path"] == scenario_root)
    root["imports"].extend(
        [
            {"path": option_aaa, "optional": True, "priority": 13},
            {"path": option_zzz, "optional": True, "priority": 13},
        ]
    )
    changed["packages"].extend(
        [
            {"import_path": option_aaa, "tag_sets": [[]], "imports": []},
            {"import_path": option_zzz, "tag_sets": [[]], "imports": []},
        ]
    )
    scenario = {
        "scenario_id": LEX_PROBE_ID,
        "tags": [],
        "roots": [scenario_root],
        "ceiling": 5,
    }
    return changed, scenario, scenario_root, option_aaa


def _tag_state(values):
    enabled = set()
    disabled = set()
    for value in values:
        if value.startswith("!"):
            name = value[1:]
            if not name or name in enabled:
                raise ValueError("conflicting or empty tag")
            disabled.add(name)
        else:
            if not value or value in disabled:
                raise ValueError("conflicting or empty tag")
            enabled.add(value)
    return enabled, disabled


def _matches(tags, clauses):
    enabled, disabled = _tag_state(tags)
    clauses = clauses or [[]]
    for clause in clauses:
        matched = True
        for term in clause:
            if term.startswith("!"):
                name = term[1:]
                if not name or name in enabled:
                    matched = False
                    break
            elif term not in enabled or term in disabled:
                matched = False
                break
        if matched:
            return True
    return False


def _resolver(replacements):
    ordered = sorted(replacements, key=lambda row: (-len(row["old"]), row["old"]))

    def resolve(path):
        current = path
        seen = {current}
        for _ in range(len(ordered) + 1):
            changed = False
            for row in ordered:
                old = row["old"]
                if current == old or current.startswith(old + "/"):
                    current = row["new"] + current[len(old) :]
                    if current in seen:
                        raise ValueError("replacement cycle")
                    seen.add(current)
                    changed = True
                    break
            if not changed:
                return current
        raise ValueError("replacement chain did not converge")

    return resolve


def _reference_plan(graph, scenario):
    resolve = _resolver(graph.get("replaces", []))
    retired = set(graph.get("retired", []))
    by_path = {row["import_path"]: row for row in graph["packages"]}
    active = {
        path
        for path, row in by_path.items()
        if path not in retired and _matches(scenario["tags"], row.get("tag_sets", [[]]))
    }
    resolved_roots = sorted(resolve(root) for root in scenario["roots"])
    if not resolved_roots or any(root not in active for root in resolved_roots):
        raise ValueError("inactive or missing root")

    options = {}
    for source, package in by_path.items():
        if source not in active:
            continue
        for edge in package.get("imports", []):
            target = resolve(edge["path"])
            if target not in by_path:
                raise ValueError("missing import target")
            if edge["optional"]:
                if not 1 <= edge["priority"] <= 1000:
                    raise ValueError("invalid optional priority")
                if target in active:
                    option_id = f"{source}->{target}"
                    if option_id in options:
                        raise ValueError("duplicate option")
                    options[option_id] = {
                        "id": option_id,
                        "from": source,
                        "to": target,
                        "priority": edge["priority"],
                    }
            elif edge["priority"] != 0:
                raise ValueError("required priority must be zero")

    def closure(selected):
        kept = set()

        def walk(path):
            target = resolve(path)
            if target not in active:
                raise ValueError("required package inactive")
            if target in kept:
                return
            kept.add(target)
            for edge in by_path[target].get("imports", []):
                resolved = resolve(edge["path"])
                if resolved not in by_path:
                    raise ValueError("missing import target")
                if resolved not in active:
                    continue
                if edge["optional"] and f"{target}->{resolved}" not in selected:
                    continue
                walk(resolved)

        for root in resolved_roots:
            walk(root)
        return kept

    mandatory = closure(set())
    if len(mandatory) > scenario["ceiling"]:
        raise ValueError("mandatory closure exceeds ceiling")
    potential = closure(set(options))
    candidates = [options[key] for key in sorted(options) if options[key]["from"] in potential]
    if len(candidates) > 20:
        raise ValueError("too many options")

    best = None
    for size in range(len(candidates) + 1):
        for combo in itertools.combinations(candidates, size):
            ids = tuple(sorted(option["id"] for option in combo))
            kept = closure(set(ids))
            if len(kept) > scenario["ceiling"]:
                continue
            if any(option["from"] not in kept for option in combo):
                continue
            score = sum(option["priority"] for option in combo)
            rank = (-score, -len(kept), ids)
            if best is None or rank < best[0]:
                best = (rank, kept, combo, score)
    if best is None:
        raise ValueError("no valid selection")

    _, kept_set, selected_combo, option_score = best
    kept = sorted(kept_set)
    dropped = sorted(set(by_path) - kept_set)
    reasons = {}
    for path in dropped:
        if path in retired:
            reasons[path] = "retired"
        elif path not in active:
            reasons[path] = "tag_excluded"
        elif path in potential:
            reasons[path] = "budget_trim"
        else:
            reasons[path] = "unreachable"
    selected_options = [
        {"from": row["from"], "to": row["to"], "priority": row["priority"]}
        for row in sorted(selected_combo, key=lambda row: row["id"])
    ]
    input_digest = _sha256(_canonical(graph) + b"\n" + _canonical(scenario))
    plan = {
        "scenario_id": scenario["scenario_id"],
        "tags": list(scenario["tags"]),
        "roots": list(scenario["roots"]),
        "resolved_roots": resolved_roots,
        "ceiling": scenario["ceiling"],
        "kept": kept,
        "dropped": dropped,
        "drop_reasons": reasons,
        "selected_options": selected_options,
        "option_score": option_score,
        "budget_used": len(kept),
        "roots_reachable": all(root in kept_set for root in resolved_roots),
        "within_budget": len(kept) <= scenario["ceiling"],
        "input_digest": input_digest,
    }
    plan["plan_digest"] = _plan_digest(plan)
    return plan


def _plan_digest(plan):
    unit = "\x1f"
    lines = [
        f"scenario_id={plan['scenario_id']}",
        f"input_digest={plan['input_digest']}",
        f"tags={unit.join(plan['tags'])}",
        f"roots={unit.join(plan['roots'])}",
        f"resolved_roots={unit.join(plan['resolved_roots'])}",
        f"ceiling={plan['ceiling']}",
        f"kept={unit.join(plan['kept'])}",
    ]
    for path in plan["dropped"]:
        lines.append(f"drop={path}:{plan['drop_reasons'][path]}")
    for option in sorted(
        plan["selected_options"], key=lambda row: f"{row['from']}->{row['to']}"
    ):
        lines.append(f"option={option['from']}->{option['to']}@{option['priority']}")
    lines.extend(
        [
            f"option_score={plan['option_score']}",
            f"budget_used={plan['budget_used']}",
            f"roots_reachable={str(plan['roots_reachable']).lower()}",
            f"within_budget={str(plan['within_budget']).lower()}",
        ]
    )
    return _sha256("\n".join(lines).encode("utf-8"))


def _report_digest(plans):
    lines = sorted(
        f"{plan['scenario_id']}|{plan['input_digest']}|{plan['plan_digest']}"
        for plan in plans
    )
    return _sha256("\n".join(lines).encode("utf-8"))


def _cache_digest(entries):
    lines = sorted(
        f"{entry['scenario_id']}|{entry['input_digest']}|{entry['plan']['plan_digest']}"
        for entry in entries
    )
    return _sha256("\n".join(lines).encode("utf-8"))


def _clear_output():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in OUTPUT_DIR.iterdir():
        if path.is_file() or path.is_symlink():
            path.unlink()


def _read_outputs():
    return tuple(
        json.loads(path.read_text(encoding="utf-8"))
        for path in (REPORT_PATH, CACHE_PATH, RUN_PATH)
    )


def _run(binary, *, expect_success=True, cwd=ENV):
    result = subprocess.run(
        [
            str(binary),
            "--all-scenarios",
            "--write",
            str(REPORT_PATH),
        ],
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
        timeout=300,
    )
    if expect_success:
        assert result.returncode == 0, result.stderr + result.stdout
        assert REPORT_PATH.exists()
        assert CACHE_PATH.exists()
        assert RUN_PATH.exists()
    else:
        assert result.returncode != 0
    return result


@contextmanager
def _patched_json(path, value):
    existed = path.exists()
    original = path.read_bytes() if existed else None
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    try:
        yield
    finally:
        if existed:
            path.write_bytes(original)
        else:
            path.unlink(missing_ok=True)


@contextmanager
def _patched_files(values):
    originals = {}
    for path, value in values.items():
        originals[path] = path.read_bytes() if path.exists() else None
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    try:
        yield
    finally:
        for path, raw in originals.items():
            if raw is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(raw)


@pytest.fixture(scope="session")
def slice_binary(tmp_path_factory):
    """Rebuild the current Go source and return the verifier-owned executable."""
    output = tmp_path_factory.mktemp("bin") / "buildslice"
    result = subprocess.run(
        ["go", "build", "-trimpath", "-o", str(output), "./cmd/slice"],
        cwd=ENV,
        capture_output=True,
        check=False,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert output.is_file()
    return output


def test_rebuilt_binary_and_exact_command_generate_all_outputs(slice_binary):
    """The rebuilt Go binary and the documented absolute command both run successfully."""
    _clear_output()
    _run(slice_binary)
    exact = subprocess.run(
        [
            "go",
            "run",
            "/app/environment/cmd/slice",
            "--all-scenarios",
            "--write",
            str(REPORT_PATH),
        ],
        cwd=APP,
        capture_output=True,
        check=False,
        text=True,
        timeout=300,
    )
    assert exact.returncode == 0, exact.stderr + exact.stdout
    assert all(path.exists() for path in (REPORT_PATH, CACHE_PATH, RUN_PATH))


def test_static_scenarios_match_independent_reference_and_drop_reasons(slice_binary):
    """Every bundled scenario matches an independent planner, including all drop reasons."""
    _clear_output()
    _run(slice_binary)
    report, cache_file, run = _read_outputs()
    graph = _load_graph()
    expected = [_reference_plan(graph, scenario) for scenario in _load_scenarios()]
    assert report["scenarios"] == expected
    assert report["summary"] == {
        "scenarios_total": len(expected),
        "all_converged": True,
        "report_digest": _report_digest(expected),
    }
    assert cache_file["entries"] == [
        {
            "scenario_id": plan["scenario_id"],
            "input_digest": plan["input_digest"],
            "plan": plan,
        }
        for plan in expected
    ]
    assert run["recomputed"] == BASELINE_IDS
    assert run["reused"] == []


def test_exact_json_schema_names_types_and_enums(slice_binary):
    """All three JSON artifacts use the exact nested field names, types, and enums."""
    _clear_output()
    _run(slice_binary)
    report, cache_file, run = _read_outputs()
    assert set(report) == {"schema_version", "command", "scenarios", "summary"}
    assert report["schema_version"] == 2 and type(report["schema_version"]) is int
    assert report["command"] == COMMAND and type(report["command"]) is str
    assert set(report["summary"]) == {
        "scenarios_total",
        "all_converged",
        "report_digest",
    }
    assert type(report["summary"]["scenarios_total"]) is int
    assert type(report["summary"]["all_converged"]) is bool
    for row in report["scenarios"]:
        assert set(row) == SCENARIO_FIELDS
        assert type(row["scenario_id"]) is str
        assert type(row["tags"]) is list
        assert type(row["roots"]) is list
        assert type(row["resolved_roots"]) is list
        assert type(row["ceiling"]) is int
        assert type(row["kept"]) is list
        assert type(row["dropped"]) is list
        assert type(row["drop_reasons"]) is dict
        assert type(row["selected_options"]) is list
        assert type(row["option_score"]) is int
        assert type(row["budget_used"]) is int
        assert type(row["roots_reachable"]) is bool
        assert type(row["within_budget"]) is bool
        assert type(row["input_digest"]) is str
        assert type(row["plan_digest"]) is str
        assert row["kept"] == sorted(row["kept"])
        assert row["dropped"] == sorted(row["dropped"])
        assert set(row["drop_reasons"]) == set(row["dropped"])
        assert set(row["drop_reasons"].values()) <= DROP_REASONS
        for option in row["selected_options"]:
            assert set(option) == {"from", "to", "priority"}
            assert type(option["from"]) is str
            assert type(option["to"]) is str
            assert type(option["priority"]) is int
    assert set(cache_file) == {"schema_version", "entries"}
    assert cache_file["schema_version"] == 1
    for entry in cache_file["entries"]:
        assert set(entry) == {"scenario_id", "input_digest", "plan"}
        assert set(entry["plan"]) == SCENARIO_FIELDS
    assert set(run) == {
        "schema_version",
        "reused",
        "recomputed",
        "removed",
        "cache_rebuilt",
        "cache_digest",
        "report_digest",
    }
    assert run["schema_version"] == 1
    assert type(run["cache_rebuilt"]) is bool


def test_sha256_digest_inputs_formats_and_cross_artifact_binding(slice_binary):
    """Input, plan, report, and cache digests bind the exact disclosed bytes."""
    _clear_output()
    _run(slice_binary)
    report, cache_file, run = _read_outputs()
    graph = _load_graph()
    scenarios = {row["scenario_id"]: row for row in _load_scenarios()}
    for plan in report["scenarios"]:
        scenario = scenarios[plan["scenario_id"]]
        assert plan["input_digest"] == _sha256(
            _canonical(graph) + b"\n" + _canonical(scenario)
        )
        assert plan["plan_digest"] == _plan_digest(plan)
        assert _is_hex64(plan["input_digest"])
        assert _is_hex64(plan["plan_digest"])
    assert report["summary"]["report_digest"] == _report_digest(report["scenarios"])
    assert run["report_digest"] == report["summary"]["report_digest"]
    assert run["cache_digest"] == _cache_digest(cache_file["entries"])
    assert _is_hex64(run["cache_digest"])


def test_global_optional_selection_and_all_tie_break_levels(slice_binary):
    """Selection maximizes global score, then budget use, then lexical edge IDs."""
    _clear_output()
    _run(slice_binary)
    report, _, _ = _read_outputs()
    rows = {row["scenario_id"]: row for row in report["scenarios"]}
    assert rows[CASE_BASE_DOCS]["selected_options"] == [
        {
            "from": ROOT_IMPORT,
            "to": DOCS_IMPORT,
            "priority": 6,
        }
    ]
    assert rows[CASE_BASE_CACHE]["selected_options"] == [
        {
            "from": ROOT_IMPORT,
            "to": CACHE_IMPORT,
            "priority": 6,
        }
    ]
    assert rows[CASE_BASE_GLOBAL]["option_score"] == 12
    assert [row["to"] for row in rows[CASE_BASE_GLOBAL]["selected_options"]] == [
        CACHE_IMPORT,
        DOCS_IMPORT,
    ]
    assert rows[CASE_INTEGRATION_TIGHT]["option_score"] == 13
    assert [row["to"] for row in rows[CASE_INTEGRATION_TIGHT]["selected_options"]] == [
        METRICS_IMPORT,
        CACHE_IMPORT,
    ]


def test_tag_activation_replacement_chain_and_closure_are_semantically_coupled(
    slice_binary,
):
    """Explicit negative tags and replacement chains affect closure and plan digests."""
    _clear_output()
    _run(slice_binary)
    report, _, _ = _read_outputs()
    rows = {row["scenario_id"]: row for row in report["scenarios"]}
    negative = rows[CASE_EXPLICIT_NEGATION]
    graph_paths = [package["import_path"] for package in _load_graph()["packages"]]
    generic_path = _path_ending(graph_paths, PLATFORM_GENERIC_SUFFIX)
    linux_path = _path_ending(graph_paths, PLATFORM_LINUX_SUFFIX)
    assert generic_path in negative["kept"]
    assert linux_path not in negative["kept"]
    replacement = rows[CASE_REPLACE_CHAIN]
    assert replacement["resolved_roots"] == [REPLACED_CLIENT_IMPORT]
    assert replacement["kept"] == [UTIL_IMPORT, REPLACED_CLIENT_IMPORT]
    assert negative["plan_digest"] != replacement["plan_digest"]


def test_dynamic_variant_defeats_hardcoded_solution(slice_binary):
    """Two fresh graph-backed scenarios force generalized planning and new digests."""
    _clear_output()
    _run(slice_binary)
    baseline_report, _, baseline_run = _read_outputs()
    graph = _load_graph()
    changed_graph, first, second = _fresh_variant(graph)
    values = {
        GRAPH_PATH: changed_graph,
        SCENARIO_DIR / f"{first['scenario_id']}.json": first,
        SCENARIO_DIR / f"{second['scenario_id']}.json": second,
    }
    with _patched_files(values):
        _run(slice_binary)
        report, cache_file, run = _read_outputs()
        expected_first = _reference_plan(changed_graph, first)
        expected_second = _reference_plan(changed_graph, second)
    rows = {row["scenario_id"]: row for row in report["scenarios"]}
    assert rows[first["scenario_id"]] == expected_first
    assert rows[second["scenario_id"]] == expected_second
    assert FRESH_ALPHA in rows[first["scenario_id"]]["kept"]
    assert FRESH_BETA in rows[second["scenario_id"]]["kept"]
    assert report["summary"]["scenarios_total"] == len(BASELINE_IDS) + 2
    assert report["summary"]["report_digest"] != baseline_report["summary"]["report_digest"]
    assert run["cache_digest"] != baseline_run["cache_digest"]
    expected_recomputed = sorted(
        BASELINE_IDS + [first["scenario_id"], second["scenario_id"]]
    )
    assert run["recomputed"] == expected_recomputed
    assert len(cache_file["entries"]) == len(BASELINE_IDS) + 2


def test_dynamic_longest_prefix_then_chain_changes_root_plan_and_digest(slice_binary):
    """A fresh root requires longest-prefix choice followed by chained replacement."""
    _clear_output()
    scenario = _replacement_probe_scenario()
    with _patched_json(SCENARIO_DIR / f"{scenario['scenario_id']}.json", scenario):
        _run(slice_binary)
        report, _, _ = _read_outputs()
        expected = _reference_plan(_load_graph(), scenario)
    row = {item["scenario_id"]: item for item in report["scenarios"]}[scenario["scenario_id"]]
    assert row == expected
    assert row["resolved_roots"] == [REPLACED_CLIENT_IMPORT]
    assert row["plan_digest"] == _plan_digest(row)


def test_warm_cache_reuses_all_and_stabilizes_every_artifact(slice_binary):
    """After a cold run, unchanged warm reruns reuse all entries byte-for-byte."""
    _clear_output()
    _run(slice_binary)
    cold_report = REPORT_PATH.read_bytes()
    cold_cache = CACHE_PATH.read_bytes()
    _run(slice_binary)
    second = tuple(path.read_bytes() for path in (REPORT_PATH, CACHE_PATH, RUN_PATH))
    _, _, warm_run = _read_outputs()
    assert warm_run["reused"] == BASELINE_IDS
    assert warm_run["recomputed"] == []
    assert warm_run["removed"] == []
    assert not warm_run["cache_rebuilt"]
    assert second[0] == cold_report
    assert second[1] == cold_cache
    _run(slice_binary)
    third = tuple(path.read_bytes() for path in (REPORT_PATH, CACHE_PATH, RUN_PATH))
    assert third == second


def test_one_manifest_change_invalidates_only_that_scenario(slice_binary):
    """A manifest edit recomputes one plan while reusing every other cache entry."""
    _clear_output()
    _run(slice_binary)
    _run(slice_binary)
    baseline_report, _, _ = _read_outputs()
    path = SCENARIO_DIR / f"{CASE_BASE_CACHE}.json"
    changed = json.loads(path.read_text(encoding="utf-8"))
    changed["ceiling"] = 7
    with _patched_json(path, changed):
        _run(slice_binary)
        report, _, run = _read_outputs()
        expected = _reference_plan(_load_graph(), changed)
    assert run["recomputed"] == [changed["scenario_id"]]
    expected_reused = sorted(set(BASELINE_IDS) - {changed["scenario_id"]})
    assert run["reused"] == expected_reused
    row = {item["scenario_id"]: item for item in report["scenarios"]}[changed["scenario_id"]]
    assert row == expected
    assert report["summary"]["report_digest"] != baseline_report["summary"]["report_digest"]


def test_graph_change_invalidates_every_cache_entry(slice_binary):
    """A graph mutation changes every input digest and forces full recomputation."""
    _clear_output()
    _run(slice_binary)
    _run(slice_binary)
    baseline_report, _, _ = _read_outputs()
    graph = _load_graph()
    changed = _clone(graph)
    root_path = _path_ending(
        [item["import_path"] for item in changed["packages"]], ROOT_SUFFIX
    )
    root = next(row for row in changed["packages"] if row["import_path"] == root_path)
    docs_path = _path_ending([item["path"] for item in root["imports"]], DOCS_SUFFIX)
    option = next(edge for edge in root["imports"] if edge["path"] == docs_path)
    option["priority"] = 11
    with _patched_json(GRAPH_PATH, changed):
        _run(slice_binary)
        report, _, run = _read_outputs()
    assert run["recomputed"] == BASELINE_IDS
    assert run["reused"] == []
    assert report["summary"]["report_digest"] != baseline_report["summary"]["report_digest"]


def test_removed_manifest_is_purged_from_cache_and_run_record(slice_binary):
    """Deleting a previously cached manifest removes its report and cache entry."""
    _clear_output()
    scenario = _stale_probe_scenario()
    path = SCENARIO_DIR / f"{scenario['scenario_id']}.json"
    with _patched_json(path, scenario):
        _run(slice_binary)
        assert scenario["scenario_id"] in {
            entry["scenario_id"] for entry in json.loads(CACHE_PATH.read_text())["entries"]
        }
    _run(slice_binary)
    report, cache_file, run = _read_outputs()
    assert run["removed"] == [scenario["scenario_id"]]
    assert scenario["scenario_id"] not in {
        row["scenario_id"] for row in report["scenarios"]
    }
    assert scenario["scenario_id"] not in {
        entry["scenario_id"] for entry in cache_file["entries"]
    }


def test_malformed_cache_recovers_without_changing_semantic_report(slice_binary):
    """An unreadable cache is discarded, rebuilt, and reported without report drift."""
    _clear_output()
    _run(slice_binary)
    baseline_report = REPORT_PATH.read_bytes()
    CACHE_PATH.write_text("{not-json\n", encoding="utf-8")
    _run(slice_binary)
    _, cache_file, run = _read_outputs()
    assert REPORT_PATH.read_bytes() == baseline_report
    assert run["cache_rebuilt"]
    assert run["recomputed"] == BASELINE_IDS
    assert run["reused"] == []
    assert run["cache_digest"] == _cache_digest(cache_file["entries"])


def test_invalid_input_fails_atomically_without_replacing_valid_outputs(slice_binary):
    """Conflicting tags fail before any valid report, cache, or run artifact is replaced."""
    _clear_output()
    _run(slice_binary)
    before = {path: path.read_bytes() for path in (REPORT_PATH, CACHE_PATH, RUN_PATH)}
    path = SCENARIO_DIR / "s05_linux.json"
    invalid = json.loads(path.read_text(encoding="utf-8"))
    invalid["tags"] = CONFLICTING_LINUX_TAGS
    with _patched_json(path, invalid):
        _run(slice_binary, expect_success=False)
    after = {path: path.read_bytes() for path in (REPORT_PATH, CACHE_PATH, RUN_PATH)}
    assert after == before


def test_dynamic_lexical_tie_break_uses_sorted_edge_ids(slice_binary):
    """Equal-score equal-budget fresh options choose the lexicographically smaller edge ID."""
    _clear_output()
    graph = _load_graph()
    changed, scenario, scenario_root, option_aaa = _lexical_variant(graph)
    values = {
        GRAPH_PATH: changed,
        SCENARIO_DIR / f"{scenario['scenario_id']}.json": scenario,
    }
    with _patched_files(values):
        _run(slice_binary)
        report, _, _ = _read_outputs()
        expected = _reference_plan(changed, scenario)
    row = {item["scenario_id"]: item for item in report["scenarios"]}[scenario["scenario_id"]]
    assert row == expected
    assert row["selected_options"] == [
        {
            "from": scenario_root,
            "to": option_aaa,
            "priority": 13,
        }
    ]

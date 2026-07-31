# ruff: noqa: I001
import functools
import hashlib
import json
import os
import pathlib
import random
import shutil
import subprocess
import tempfile

import pytest


BINARY = pathlib.Path("/app/bin/drainwave")
AGENT_UID = 10001
AGENT_GID = 10001


@pytest.fixture(scope="session", autouse=True)
def rebuild_candidate():
    """Rebuild the submitted Go source as an unprivileged account before verification."""
    session = os.getpid()
    home = pathlib.Path(f"/tmp/drainwave-home-{session}")
    cache = pathlib.Path(f"/tmp/drainwave-gocache-{session}")
    binary_dir = BINARY.parent
    for path in (home, cache, binary_dir):
        path.mkdir(parents=True, exist_ok=True)
        if os.geteuid() == 0:
            os.chown(path, AGENT_UID, AGENT_GID)
        path.chmod(0o700 if path != binary_dir else 0o755)
    BINARY.unlink(missing_ok=True)
    command = ["env", f"HOME={home}", f"GOCACHE={cache}", "/app/build.sh"]
    if os.geteuid() == 0:
        command = [
            "setpriv",
            f"--reuid={AGENT_UID}",
            f"--regid={AGENT_GID}",
            "--clear-groups",
            *command,
        ]
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr.decode()
    yield
    shutil.rmtree(home, ignore_errors=True)
    shutil.rmtree(cache, ignore_errors=True)


@pytest.fixture
def case_dir():
    """Provide a fresh verifier-owned directory traversable by the unprivileged product."""
    path = pathlib.Path(tempfile.mkdtemp(prefix="drainwave-case-", dir="/tmp"))
    path.chmod(0o777)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def node(node_id, zone="z1", rack="r1", power=1, services=None):
    return {
        "id": node_id,
        "zone": zone,
        "rack": rack,
        "power": power,
        "services": services or ["base"],
    }


def separation(left, right, gap):
    return {"left": left, "right": right, "gap": gap}


def rolling(window, maximum):
    return {"window": window, "max_unavailable": maximum}


def policy(
    targets,
    *,
    minimum=None,
    zones=None,
    racks=None,
    cooldown=None,
    precedence=None,
    cohorts=None,
    separations=None,
    rolling_limits=None,
    risk_weights=None,
    size=2,
):
    return {
        "targets": targets,
        "min_available": minimum if minimum is not None else {},
        "zone_parallel": zones if zones is not None else {"z1": len(targets)},
        "rack_power_limit": racks if racks is not None else {"r1": 1_000_000},
        "cooldown": cooldown if cooldown is not None else {},
        "precedence": precedence if precedence is not None else [],
        "cohorts": cohorts if cohorts is not None else [],
        "separation": separations if separations is not None else [],
        "rolling_limits": rolling_limits if rolling_limits is not None else {},
        "risk_weights": risk_weights if risk_weights is not None else {},
        "max_wave_size": size,
    }


def run_raw(arguments):
    command = [str(BINARY), *map(str, arguments)]
    if os.geteuid() == 0:
        command = [
            "setpriv",
            f"--reuid={AGENT_UID}",
            f"--regid={AGENT_GID}",
            "--clear-groups",
            *command,
        ]
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        timeout=35,
    )


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    path.chmod(0o644)


def invoke(case_dir, inventory, rules):
    inventory_path = case_dir / "inventory.json"
    policy_path = case_dir / "policy.json"
    output_path = case_dir / "nested" / "plan.json"
    write_json(inventory_path, inventory)
    write_json(policy_path, rules)
    result = run_raw([inventory_path, policy_path, output_path])
    raw = output_path.read_bytes() if output_path.exists() else None
    report = json.loads(raw) if raw is not None else None
    return result, report, raw


def reference_schedule(inventory, rules):
    nodes = {item["id"]: item for item in inventory["nodes"]}
    targets = sorted(rules["targets"])
    position = {name: index for index, name in enumerate(targets)}
    predecessors = [0] * len(targets)
    for before, after in rules["precedence"]:
        predecessors[position[after]] |= 1 << position[before]

    cohort_masks = []
    for cohort in rules["cohorts"]:
        mask = 0
        for name in cohort:
            mask |= 1 << position[name]
        cohort_masks.append(mask)

    separation_rules = [
        (1 << position[item["left"]], 1 << position[item["right"]], item["gap"])
        for item in rules["separation"]
    ]
    totals = {}
    for item in inventory["nodes"]:
        for service in item["services"]:
            totals[service] = totals.get(service, 0) + 1
    cooldown_keys = sorted(rules["cooldown"])
    history_depth = max(
        [0]
        + [item["gap"] for item in rules["separation"]]
        + [item["window"] - 1 for item in rules["rolling_limits"].values()]
    )

    def names(mask):
        return tuple(name for index, name in enumerate(targets) if mask & (1 << index))

    @functools.cache
    def service_count(mask, service):
        return sum(service in nodes[name]["services"] for name in names(mask))

    def services(mask):
        return {
            service
            for name in names(mask)
            for service in nodes[name]["services"]
        }

    def eligible(mask, completed):
        return all(
            not mask & (1 << index)
            or predecessors[index] & completed == predecessors[index]
            for index in range(len(targets))
        )

    def valid_static(mask):
        selected = names(mask)
        if not selected or len(selected) > rules["max_wave_size"]:
            return False
        for cohort in cohort_masks:
            intersection = mask & cohort
            if intersection not in (0, cohort):
                return False
        if any(mask & left and mask & right for left, right, _ in separation_rules):
            return False
        zones = {}
        racks = {}
        unavailable = {}
        for name in selected:
            item = nodes[name]
            zones[item["zone"]] = zones.get(item["zone"], 0) + 1
            racks[item["rack"]] = racks.get(item["rack"], 0) + item["power"]
            for service in item["services"]:
                unavailable[service] = unavailable.get(service, 0) + 1
        if any(count > rules["zone_parallel"][zone] for zone, count in zones.items()):
            return False
        if any(power > rules["rack_power_limit"][rack] for rack, power in racks.items()):
            return False
        return all(
            totals.get(service, 0) - unavailable.get(service, 0) >= minimum
            for service, minimum in rules["min_available"].items()
        )

    def cooldown_allows(mask, cooldown_state):
        selected_services = services(mask)
        return all(
            cooldown_state[index] == 0 or service not in selected_services
            for index, service in enumerate(cooldown_keys)
        )

    def next_cooldown(mask, cooldown_state):
        selected_services = services(mask)
        next_state = [max(value - 1, 0) for value in cooldown_state]
        for index, service in enumerate(cooldown_keys):
            if service in selected_services:
                next_state[index] = max(next_state[index], rules["cooldown"][service])
        return tuple(next_state)

    def separation_allows(mask, completed, recent):
        for left, right, gap in separation_rules:
            left_now = bool(mask & left)
            right_now = bool(mask & right)
            if left_now and right_now:
                return False
            earlier = 0
            if left_now and completed & right:
                earlier = right
            elif right_now and completed & left:
                earlier = left
            if earlier and any(previous & earlier for previous in recent[:gap]):
                return False
        return True

    def rolling_allows(mask, recent):
        for service, limit in rules["rolling_limits"].items():
            count = service_count(mask, service)
            count += sum(
                service_count(previous, service)
                for previous in recent[: limit["window"] - 1]
            )
            if count > limit["max_unavailable"]:
                return False
        return True

    def wave_risk(mask):
        return sum(
            weight * service_count(mask, service) ** 2
            for service, weight in rules["risk_weights"].items()
        )

    full = (1 << len(targets)) - 1

    @functools.cache
    def solve(completed, cooldown_state, recent):
        if completed == full:
            return (), 0
        remaining = full ^ completed
        best = None
        subset = remaining
        while subset:
            if (
                eligible(subset, completed)
                and valid_static(subset)
                and cooldown_allows(subset, cooldown_state)
                and separation_allows(subset, completed, recent)
                and rolling_allows(subset, recent)
            ):
                next_recent = ((subset,) + recent)[:history_depth] if history_depth else ()
                suffix = solve(completed | subset, next_cooldown(subset, cooldown_state), next_recent)
                if suffix is not None:
                    suffix_waves, suffix_risk = suffix
                    candidate_waves = (names(subset),) + suffix_waves
                    candidate_risk = wave_risk(subset) + suffix_risk
                    key = (len(candidate_waves), candidate_risk, candidate_waves)
                    if best is None or key < best[0]:
                        best = (key, candidate_waves, candidate_risk)
            subset = (subset - 1) & remaining
        if best is None:
            return None
        return best[1], best[2]

    answer = solve(
        0,
        tuple(0 for _ in cooldown_keys),
        tuple(0 for _ in range(history_depth)),
    )
    return None if answer is None else [list(wave) for wave in answer[0]]


def digest_source(waves):
    def render(values):
        return ",".join(f"{key}={values[key]}" for key in sorted(values))

    lines = []
    for wave in waves:
        lines.append(
            "{}|{}|{}|{}|{}|{}|{}|{}\n".format(
                wave["wave"],
                ",".join(wave["nodes"]),
                render(wave["unavailable_services"]),
                render(wave["zone_counts"]),
                render(wave["rack_power"]),
                render(wave["cooldown_after"]),
                render(wave["rolling_unavailable"]),
                wave["wave_risk"],
            )
        )
    return "".join(lines).encode("utf-8")


def plan_digest(waves):
    return "sha256:" + hashlib.sha256(digest_source(waves)).hexdigest()


def expected_report(inventory, rules):
    schedule = reference_schedule(inventory, rules)
    if schedule is None:
        return {"status": "unsatisfiable", "reason": "no_valid_schedule"}
    nodes = {item["id"]: item for item in inventory["nodes"]}
    reports = []
    cooldown_state = {service: 0 for service in rules["cooldown"]}
    recent_unavailable = []
    schedule_risk = 0
    for index, names in enumerate(schedule, 1):
        all_unavailable = {}
        unavailable = {service: 0 for service in rules["min_available"]}
        zones = {}
        racks = {}
        for name in names:
            item = nodes[name]
            zones[item["zone"]] = zones.get(item["zone"], 0) + 1
            racks[item["rack"]] = racks.get(item["rack"], 0) + item["power"]
            for service in item["services"]:
                all_unavailable[service] = all_unavailable.get(service, 0) + 1
                if service in unavailable:
                    unavailable[service] += 1
        for service, value in cooldown_state.items():
            cooldown_state[service] = max(value - 1, 0)
        for service in all_unavailable:
            if service in cooldown_state:
                cooldown_state[service] = max(
                    cooldown_state[service], rules["cooldown"][service]
                )
        rolling_counts = {}
        for service, limit in rules["rolling_limits"].items():
            rolling_counts[service] = all_unavailable.get(service, 0) + sum(
                previous.get(service, 0)
                for previous in recent_unavailable[: limit["window"] - 1]
            )
        wave_risk = sum(
            weight * all_unavailable.get(service, 0) ** 2
            for service, weight in rules["risk_weights"].items()
        )
        schedule_risk += wave_risk
        reports.append(
            {
                "wave": index,
                "nodes": names,
                "unavailable_services": unavailable,
                "zone_counts": zones,
                "rack_power": racks,
                "cooldown_after": dict(cooldown_state),
                "rolling_unavailable": rolling_counts,
                "wave_risk": wave_risk,
            }
        )
        recent_unavailable.insert(0, all_unavailable)
        del recent_unavailable[3:]
    return {
        "status": "ok",
        "wave_count": len(reports),
        "schedule_risk": schedule_risk,
        "plan_digest": plan_digest(reports),
        "waves": reports,
    }


def assert_report_contract(report, raw, rules):
    assert set(report) == {"status", "wave_count", "schedule_risk", "plan_digest", "waves"}
    assert report["status"] == "ok"
    assert type(report["wave_count"]) is int and report["wave_count"] > 0
    assert type(report["schedule_risk"]) is int and report["schedule_risk"] >= 0
    assert isinstance(report["plan_digest"], str)
    assert report["plan_digest"].startswith("sha256:")
    assert len(report["plan_digest"]) == 71
    assert report["plan_digest"] == report["plan_digest"].lower()
    assert isinstance(report["waves"], list)
    for index, wave in enumerate(report["waves"], 1):
        assert set(wave) == {
            "wave",
            "nodes",
            "unavailable_services",
            "zone_counts",
            "rack_power",
            "cooldown_after",
            "rolling_unavailable",
            "wave_risk",
        }
        assert wave["wave"] == index and type(wave["wave"]) is int
        assert isinstance(wave["nodes"], list) and wave["nodes"] == sorted(wave["nodes"])
        assert isinstance(wave["unavailable_services"], dict)
        assert isinstance(wave["zone_counts"], dict)
        assert isinstance(wave["rack_power"], dict)
        assert isinstance(wave["cooldown_after"], dict)
        assert isinstance(wave["rolling_unavailable"], dict)
        assert type(wave["wave_risk"]) is int
        assert set(wave["unavailable_services"]) == set(rules["min_available"])
        assert set(wave["cooldown_after"]) == set(rules["cooldown"])
        assert set(wave["rolling_unavailable"]) == set(rules["rolling_limits"])
        for mapping in (
            wave["unavailable_services"],
            wave["zone_counts"],
            wave["rack_power"],
            wave["cooldown_after"],
            wave["rolling_unavailable"],
        ):
            assert all(type(value) is int for value in mapping.values())
    assert report["schedule_risk"] == sum(wave["wave_risk"] for wave in report["waves"])
    assert report["plan_digest"] == plan_digest(report["waves"])
    assert raw == json.dumps(report, separators=(",", ":"), ensure_ascii=False).encode() + b"\n"


def assert_success(case_dir, inventory, rules):
    result, report, raw = invoke(case_dir, inventory, rules)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == b"" and result.stderr == b""
    assert report == expected_report(inventory, rules)
    assert_report_contract(report, raw, rules)
    return report


def assert_unsatisfiable(case_dir, inventory, rules):
    result, report, raw = invoke(case_dir, inventory, rules)
    assert result.returncode == 3
    assert result.stdout == b"" and result.stderr == b""
    assert report == {"status": "unsatisfiable", "reason": "no_valid_schedule"}
    assert raw == b'{"status":"unsatisfiable","reason":"no_valid_schedule"}\n'


def test_rebuild_produces_native_executable():
    """The verifier rebuild must produce an executable ELF rather than a script or stale shim."""
    assert BINARY.is_file()
    assert os.access(BINARY, os.X_OK)
    assert BINARY.read_bytes()[:4] == b"\x7fELF"


def test_greedy_maximal_wave_is_not_minimum(case_dir):
    """A maximal first wave must not replace global wave-count minimisation."""
    inventory = {
        "nodes": [
            node("a", services=["ad"]),
            node("b", services=["bc"]),
            node("c", services=["bc", "cd"]),
            node("d", services=["ad", "cd"]),
        ]
    }
    rules = policy(
        ["d", "b", "a", "c"],
        minimum={"ad": 1, "bc": 1, "cd": 1},
        size=2,
    )
    report = assert_success(case_dir, inventory, rules)
    assert report["wave_count"] == 2
    assert [wave["nodes"] for wave in report["waves"]] == [["a", "c"], ["b", "d"]]


def test_lexicographic_tie_break_ignores_all_input_order(case_dir):
    """Target, node, cohort, and policy ordering must not alter the canonical equal-score plan."""
    inventory = {"nodes": [node(name) for name in ["δ", "b", "a", "c"]]}
    rules = policy(
        ["δ", "c", "b", "a"],
        cohorts=[["b", "a"]],
        size=2,
    )
    first = assert_success(case_dir, inventory, rules)
    inventory["nodes"].reverse()
    rules["targets"].reverse()
    rules["cohorts"][0].reverse()
    second = assert_success(case_dir, inventory, rules)
    assert [wave["nodes"] for wave in first["waves"]] == [["a", "b"], ["c", "δ"]]
    assert first == second


def test_cohort_precedence_rolling_and_digest_are_coupled(case_dir):
    """Atomic cohorts must survive precedence and rolling checks through report and digest generation."""
    inventory = {
        "nodes": [
            node("api-a", "east", "r1", 2, ["api"]),
            node("api-b", "west", "r2", 2, ["api"]),
            node("job-a", "east", "r3", 1, ["job"]),
            node("job-b", "west", "r4", 1, ["job"]),
            node("bridge", "central", "r5", 1, ["bridge"]),
            node("steady", "central", "r6", 1, ["api", "job"]),
        ]
    }
    rules = policy(
        ["job-b", "api-b", "bridge", "job-a", "api-a"],
        minimum={"api": 1, "job": 1},
        zones={"east": 2, "west": 2, "central": 1},
        racks={"r1": 2, "r2": 2, "r3": 1, "r4": 1, "r5": 1},
        precedence=[["api-a", "api-b"]],
        cohorts=[["job-b", "job-a"]],
        rolling_limits={"api": rolling(2, 1)},
        risk_weights={"api": 5, "job": 2},
        size=2,
    )
    report = assert_success(case_dir, inventory, rules)
    waves = [wave["nodes"] for wave in report["waves"]]
    assert ["job-a", "job-b"] in waves
    assert waves.index(["api-a"]) < next(index for index, wave in enumerate(waves) if "api-b" in wave)
    assert all(wave["rolling_unavailable"]["api"] <= 1 for wave in report["waves"])
    assert report["schedule_risk"] == 18
    assert report["plan_digest"] == plan_digest(report["waves"])


def test_separation_cooldown_and_rolling_require_reserved_gap_waves(case_dir):
    """Gap nodes must be reserved when separation, cooldown, and a rolling budget all constrain one service."""
    inventory = {
        "nodes": [
            node("hot-first", "z1", "r1", 1, ["hot"]),
            node("hot-last", "z2", "r2", 1, ["hot"]),
            node("gap-a", "z1", "r3", 1, ["left"]),
            node("gap-b", "z2", "r4", 1, ["right"]),
            node("steady", "z3", "r5", 1, ["hot", "left", "right"]),
        ]
    }
    rules = policy(
        ["hot-last", "gap-b", "gap-a", "hot-first"],
        minimum={"hot": 1, "left": 1, "right": 1},
        zones={"z1": 1, "z2": 1},
        racks={"r1": 1, "r2": 1, "r3": 1, "r4": 1},
        cooldown={"hot": 2},
        precedence=[["hot-first", "hot-last"]],
        separations=[separation("hot-first", "hot-last", 2)],
        rolling_limits={"hot": rolling(3, 1)},
        risk_weights={"hot": 4},
        size=2,
    )
    report = assert_success(case_dir, inventory, rules)
    assert [wave["nodes"] for wave in report["waves"]] == [
        ["hot-first"],
        ["gap-a"],
        ["gap-b"],
        ["hot-last"],
    ]
    assert [wave["cooldown_after"]["hot"] for wave in report["waves"]] == [2, 1, 0, 2]


def test_risk_objective_beats_lexicographic_only_schedule(case_dir):
    """Equal-wave schedules must minimise quadratic service concentration before lexicographic order."""
    inventory = {
        "nodes": [
            node("a-hot", services=["hot"]),
            node("b-hot", services=["hot"]),
            node("c-cold", services=["cold"]),
            node("d-cold", services=["cold"]),
            node("steady", "z2", "r2", 1, ["hot", "cold"]),
        ]
    }
    rules = policy(
        ["d-cold", "c-cold", "b-hot", "a-hot"],
        minimum={"hot": 1, "cold": 1},
        risk_weights={"hot": 10, "cold": 1},
        size=2,
    )
    report = assert_success(case_dir, inventory, rules)
    assert [wave["nodes"] for wave in report["waves"]] == [
        ["a-hot", "c-cold"],
        ["b-hot", "d-cold"],
    ]
    assert report["schedule_risk"] == 22


def test_history_state_distinguishes_same_completed_set(case_dir):
    """Recent-wave history, not only the completed set, must control future rolling and separation legality."""
    inventory = {
        "nodes": [
            node("a", services=["api"]),
            node("b", services=["worker"]),
            node("c", services=["api"]),
            node("d", services=["worker"]),
            node("steady", "z2", "r2", 1, ["api", "worker"]),
        ]
    }
    rules = policy(
        ["d", "c", "b", "a"],
        precedence=[["a", "d"]],
        separations=[separation("a", "c", 1)],
        rolling_limits={"api": rolling(2, 1)},
        size=1,
    )
    report = assert_success(case_dir, inventory, rules)
    assert [wave["nodes"] for wave in report["waves"]] == [["a"], ["b"], ["c"], ["d"]]


def test_zero_cooldown_and_window_one_require_no_extra_gap(case_dir):
    """Cooldown zero and a one-wave rolling window constrain batching without adding wait waves."""
    inventory = {
        "nodes": [
            node("a", services=["api"]),
            node("b", services=["api"]),
            node("c", services=["worker"]),
            node("steady", "z2", "r2", 1, ["api", "worker"]),
        ]
    }
    rules = policy(
        ["c", "b", "a"],
        cooldown={"api": 0},
        separations=[separation("a", "b", 0)],
        rolling_limits={"api": rolling(1, 1)},
        size=2,
    )
    report = assert_success(case_dir, inventory, rules)
    assert [wave["nodes"] for wave in report["waves"]] == [["a"], ["b", "c"]]
    assert [wave["cooldown_after"]["api"] for wave in report["waves"]] == [0, 0]


def test_dynamic_variant_defeats_hardcoded_solution(case_dir):
    """Two fresh named policies must change nodes, classifications, summary risk, digest, and raw checksum."""
    base_inventory = {"nodes": [node("sample-a"), node("sample-b")]}
    base_rules = policy(["sample-a", "sample-b"], size=1)
    base_report = assert_success(case_dir, base_inventory, base_rules)
    seen_digests = {base_report["plan_digest"]}
    seen_checksums = set()
    for label in ("amber-41", "cobalt-73"):
        api_a = f"{label}-api-a"
        api_b = f"{label}-api-b"
        pair_a = f"{label}-pair-a"
        pair_b = f"{label}-pair-b"
        gap = f"{label}-gap"
        inventory = {
            "nodes": [
                node(api_a, "za", "ra", 2, [f"{label}-api"]),
                node(api_b, "zb", "rb", 2, [f"{label}-api"]),
                node(pair_a, "za", "rc", 1, [f"{label}-job"]),
                node(pair_b, "zb", "rd", 1, [f"{label}-job"]),
                node(gap, "zc", "re", 1, [f"{label}-gap"]),
                node(f"{label}-steady", "zd", "rf", 1, [f"{label}-api", f"{label}-job"]),
            ]
        }
        rules = policy(
            [api_b, pair_b, gap, pair_a, api_a],
            minimum={f"{label}-api": 1, f"{label}-job": 1},
            zones={"za": 2, "zb": 2, "zc": 1},
            racks={"ra": 2, "rb": 2, "rc": 1, "rd": 1, "re": 1},
            precedence=[[api_a, api_b]],
            cohorts=[[pair_b, pair_a]],
            separations=[separation(api_a, api_b, 1)],
            rolling_limits={f"{label}-api": rolling(2, 1)},
            risk_weights={f"{label}-api": 7, f"{label}-job": 2},
            size=2,
        )
        result, report, raw = invoke(case_dir, inventory, rules)
        assert result.returncode == 0, result.stderr.decode()
        assert report == expected_report(inventory, rules)
        flattened = {name for wave in report["waves"] for name in wave["nodes"]}
        assert {api_a, api_b, pair_a, pair_b, gap} == flattened
        assert [pair_a, pair_b] in [wave["nodes"] for wave in report["waves"]]
        assert report["wave_count"] == 3
        assert report["schedule_risk"] == 22
        assert report["plan_digest"] not in seen_digests
        seen_digests.add(report["plan_digest"])
        checksum = hashlib.sha256(raw).hexdigest()
        assert checksum not in seen_checksums
        seen_checksums.add(checksum)


def test_dynamic_twelve_target_scaling_defeats_exponential_state_search(case_dir):
    """Two fresh maximum-size rolling policies must be solved exactly without unpruned history-state explosion."""
    variants = (
        ("quartz-17", [0] * 4 + [1] * 4 + [2] * 4),
        ("sable-29", [0, 1, 0, 2, 1, 2, 0, 2, 1, 0, 1, 2]),
    )
    seen_digests = set()
    seen_checksums = set()
    for label, assignment in variants:
        nodes = [
            node(
                f"{label}-{index:02d}",
                f"z{service}",
                f"r{index % 4}",
                1,
                [f"{label}-svc{service}"],
            )
            for index, service in enumerate(assignment)
        ]
        inventory = {"nodes": list(reversed(nodes))}
        target_order = [item["id"] for item in nodes[5:] + nodes[:5]]
        rules = policy(
            target_order,
            zones={"z0": 12, "z1": 12, "z2": 12},
            racks={"r0": 12, "r1": 12, "r2": 12, "r3": 12},
            rolling_limits={
                f"{label}-svc0": rolling(3, 2),
                f"{label}-svc1": rolling(3, 2),
                f"{label}-svc2": rolling(3, 2),
            },
            risk_weights={
                f"{label}-svc0": 1,
                f"{label}-svc1": 2,
                f"{label}-svc2": 3,
            },
            size=3,
        )
        expected_indices = (
            [[0], [1, 4, 8], [5, 9], [2], [3, 6, 10], [7, 11]]
            if assignment == [0] * 4 + [1] * 4 + [2] * 4
            else [[0], [1, 2, 3], [4, 5], [6], [7, 8], [9, 10, 11]]
        )
        expected_waves = [
            [f"{label}-{index:02d}" for index in wave]
            for wave in expected_indices
        ]

        result, report, raw = invoke(case_dir, inventory, rules)
        assert result.returncode == 0, result.stderr.decode()
        assert result.stdout == b"" and result.stderr == b""
        assert_report_contract(report, raw, rules)
        assert report["wave_count"] == 6
        assert report["schedule_risk"] == 24
        assert [wave["nodes"] for wave in report["waves"]] == expected_waves
        assert {name for wave in expected_waves for name in wave} == set(target_order)
        assert all(
            count <= 2
            for wave in report["waves"]
            for count in wave["rolling_unavailable"].values()
        )
        assert report["plan_digest"] not in seen_digests
        seen_digests.add(report["plan_digest"])
        checksum = hashlib.sha256(raw).hexdigest()
        assert checksum not in seen_checksums
        seen_checksums.add(checksum)


def test_dynamic_separation_reserve_defeats_local_greedy_solution(case_dir):
    """Fresh gap-two cases must keep two filler waves available instead of consuming them together."""
    for label in ("north", "south"):
        first = f"{label}-first"
        last = f"{label}-last"
        filler_a = f"{label}-filler-a"
        filler_b = f"{label}-filler-b"
        inventory = {
            "nodes": [
                node(first, services=["hot"]),
                node(last, "z2", "r2", 1, ["hot"]),
                node(filler_a, services=["cold-a"]),
                node(filler_b, "z2", "r2", 1, ["cold-b"]),
                node(f"{label}-steady", "z3", "r3", 1, ["hot", "cold-a", "cold-b"]),
            ]
        }
        rules = policy(
            [last, filler_b, filler_a, first],
            zones={"z1": 2, "z2": 2},
            racks={"r1": 2, "r2": 2},
            precedence=[[first, last]],
            separations=[separation(first, last, 2)],
            size=2,
        )
        report = assert_success(case_dir, inventory, rules)
        assert [wave["nodes"] for wave in report["waves"]] == [
            [first],
            [filler_a],
            [filler_b],
            [last],
        ]


def test_seeded_generated_policies_match_independent_solver(case_dir):
    """Seeded unseen inventories exercise combined constraints against an independent exact solver."""
    rng = random.Random(6_118_027)
    for scenario in range(8):
        count = 5 + scenario % 3
        names = [f"g{scenario}-{index}" for index in range(count)]
        inventory_nodes = []
        for index, name in enumerate(names):
            services = [f"svc-{index % 3}"]
            if rng.randrange(4) == 0:
                services.append(f"svc-{(index + 1) % 3}")
            inventory_nodes.append(
                node(name, f"z{index % 2}", f"r{index % 3}", 1 + rng.randrange(3), services)
            )
        inventory_nodes.append(node(f"stable-{scenario}", "z2", "r3", 1, ["svc-0", "svc-1", "svc-2"]))
        inventory = {"nodes": inventory_nodes}
        precedence = [[names[0], names[-1]]] if scenario % 2 else []
        cohorts = [[names[1], names[2]]] if scenario in (2, 5) else []
        separations = [separation(names[0], names[-1], 1)] if scenario in (1, 4, 7) else []
        rolling_limits = {"svc-0": rolling(2 + scenario % 2, 2)} if scenario >= 3 else {}
        cooldown = {"svc-1": 1} if scenario in (3, 6) else {}
        rules = policy(
            list(reversed(names)),
            minimum={"svc-0": 1, "svc-1": 1, "svc-2": 1},
            zones={"z0": 2, "z1": 2},
            racks={"r0": 5, "r1": 5, "r2": 5},
            cooldown=cooldown,
            precedence=precedence,
            cohorts=cohorts,
            separations=separations,
            rolling_limits=rolling_limits,
            risk_weights={"svc-0": 3, "svc-1": 2, "svc-2": 1},
            size=2 + scenario % 2,
        )
        expected = expected_report(inventory, rules)
        result, report, raw = invoke(case_dir, inventory, rules)
        assert report == expected
        if expected["status"] == "ok":
            assert result.returncode == 0
            assert raw.endswith(b"\n")
        else:
            assert result.returncode == 3


def test_valid_but_incompatible_rules_are_unsatisfiable(case_dir):
    """Cycles, oversized cohorts, and impossible rolling histories are valid policies with no schedule."""
    cases = []
    inventory = {"nodes": [node("a"), node("b"), node("c")]}
    cases.append((inventory, policy(["a", "b", "c"], precedence=[["a", "b"], ["b", "c"], ["c", "a"]], size=2)))
    cases.append((inventory, policy(["a", "b", "c"], cohorts=[["a", "b", "c"]], size=2)))
    rolling_inventory = {
        "nodes": [node("a", services=["api"]), node("b", services=["api"]), node("steady", "z2", "r2", 1, ["api"])]
    }
    cases.append(
        (
            rolling_inventory,
            policy(
                ["a", "b"],
                precedence=[["a", "b"]],
                rolling_limits={"api": rolling(2, 1)},
                size=1,
            ),
        )
    )
    for current_inventory, rules in cases:
        assert_unsatisfiable(case_dir, current_inventory, rules)


def test_invalid_schema_variants_preserve_output(case_dir):
    """Original and extended schema violations must exit two without changing existing bytes."""
    mutations = [
        lambda inv, rules: inv.update(nodes=[]),
        lambda inv, rules: inv.update(nodes=[node("a"), node("b")] + [node(f"x-{index}") for index in range(255)]),
        lambda inv, rules: inv["nodes"].append(dict(inv["nodes"][0])),
        lambda inv, rules: inv["nodes"][0].update(id=""),
        lambda inv, rules: inv["nodes"][0].update(zone=""),
        lambda inv, rules: inv["nodes"][0].update(rack=""),
        lambda inv, rules: inv["nodes"][0].update(power=0),
        lambda inv, rules: inv["nodes"][0].update(power=1_000_001),
        lambda inv, rules: inv["nodes"][0].update(services=[]),
        lambda inv, rules: inv["nodes"][0].update(services=[f"svc-{index}" for index in range(33)]),
        lambda inv, rules: inv["nodes"][0].update(services=["api", "api"]),
        lambda inv, rules: inv["nodes"][0].update(extra=True),
        lambda inv, rules: rules.update(targets=[]),
        lambda inv, rules: (inv.update(nodes=[node(f"n-{index}") for index in range(13)]), rules.update(targets=[f"n-{index}" for index in range(13)], max_wave_size=1)),
        lambda inv, rules: rules.update(targets=["a", "a"]),
        lambda inv, rules: rules["min_available"].update(api=-1),
        lambda inv, rules: rules["min_available"].update({"": 0}),
        lambda inv, rules: rules["rack_power_limit"].update(r1=1_000_001),
        lambda inv, rules: rules["zone_parallel"].clear(),
        lambda inv, rules: rules.update(precedence=[["a"]]),
        lambda inv, rules: rules.update(precedence=[["a", "a"]]),
        lambda inv, rules: rules.update(precedence=[["a", "missing"]]),
        lambda inv, rules: rules.update(precedence=[["a", "b"], ["a", "b"]]),
        lambda inv, rules: rules.update(targets=["a", "missing"]),
        lambda inv, rules: rules.update(max_wave_size="2"),
        lambda inv, rules: rules.update(extra=True),
        lambda inv, rules: rules.pop("cooldown"),
        lambda inv, rules: rules.pop("precedence"),
        lambda inv, rules: rules.pop("cohorts"),
        lambda inv, rules: rules.update(cohorts=None),
        lambda inv, rules: rules.update(separation=None),
        lambda inv, rules: rules.update(rolling_limits=None),
        lambda inv, rules: rules.update(risk_weights=None),
    ]
    for mutation in mutations:
        inventory = {"nodes": [node("a", services=["api"]), node("b", services=["api"])]}
        rules = policy(["a", "b"], minimum={"api": 1}, size=1)
        mutation(inventory, rules)
        inventory_path = case_dir / "inventory.json"
        policy_path = case_dir / "policy.json"
        output_path = case_dir / "output.json"
        write_json(inventory_path, inventory)
        write_json(policy_path, rules)
        output_path.write_text("keep-me", encoding="utf-8")
        output_path.chmod(0o666)
        result = run_raw([inventory_path, policy_path, output_path])
        assert result.returncode == 2
        assert result.stdout == b""
        assert result.stderr == b"drainwave: invalid input\n"
        assert output_path.read_text(encoding="utf-8") == "keep-me"


def test_invalid_new_policy_values_preserve_output(case_dir):
    """Cohort, separation, rolling, cooldown, and risk bounds must be validated exactly."""
    mutations = [
        lambda rules: rules.update(cohorts=[["a"]]),
        lambda rules: rules.update(cohorts=[["a", "b", "c", "a", "b"]]),
        lambda rules: rules.update(cohorts=[["a", "a"]]),
        lambda rules: rules.update(cohorts=[["a", "b"], ["b", "c"]]),
        lambda rules: rules.update(cohorts=[["a", "missing"]]),
        lambda rules: rules.update(separation=[separation("a", "a", 1)]),
        lambda rules: rules.update(separation=[separation("a", "missing", 1)]),
        lambda rules: rules.update(separation=[separation("a", "b", 4)]),
        lambda rules: rules.update(separation=[separation("a", "b", 1), separation("b", "a", 2)]),
        lambda rules: rules.update(separation=[{"left": "a", "right": "b", "gap": 1, "extra": 0}]),
        lambda rules: rules.update(separation=[{"left": "a", "right": "b", "gap": "1"}]),
        lambda rules: rules.update(rolling_limits={"api": rolling(0, 1)}),
        lambda rules: rules.update(rolling_limits={"api": rolling(5, 1)}),
        lambda rules: rules.update(rolling_limits={"api": rolling(2, -1)}),
        lambda rules: rules.update(rolling_limits={"api": rolling(2, 1_000_001)}),
        lambda rules: rules.update(rolling_limits={"": rolling(2, 1)}),
        lambda rules: rules.update(rolling_limits={f"svc-{index}": rolling(1, 1) for index in range(17)}),
        lambda rules: rules.update(rolling_limits={"api": {"window": 2, "max_unavailable": 1, "extra": 0}}),
        lambda rules: rules.update(risk_weights={"api": 0}),
        lambda rules: rules.update(risk_weights={"api": 1001}),
        lambda rules: rules.update(risk_weights={"": 1}),
        lambda rules: rules.update(risk_weights={f"svc-{index}": 1 for index in range(17)}),
        lambda rules: rules.update(cooldown={"api": 4}),
        lambda rules: rules.update(cooldown={"": 1}),
        lambda rules: rules.update(cooldown={f"svc-{index}": 1 for index in range(17)}),
        lambda rules: rules.update(max_wave_size=4),
        lambda rules: rules.update(cohorts=[["a", "b"]], separation=[separation("a", "b", 1)], max_wave_size=0),
    ]
    inventory = {"nodes": [node("a"), node("b"), node("c")]}
    for mutation in mutations:
        rules = policy(["a", "b", "c"], size=2)
        mutation(rules)
        inventory_path = case_dir / "inventory.json"
        policy_path = case_dir / "policy.json"
        output_path = case_dir / "output.json"
        write_json(inventory_path, inventory)
        write_json(policy_path, rules)
        output_path.write_bytes(b"sentinel")
        output_path.chmod(0o666)
        result = run_raw([inventory_path, policy_path, output_path])
        assert result.returncode == 2
        assert result.stderr == b"drainwave: invalid input\n"
        assert output_path.read_bytes() == b"sentinel"


def test_empty_tracking_maps_remain_explicit_in_success_schema(case_dir):
    """A policy with empty service maps still emits all required empty nested objects and zero risk."""
    inventory = {"nodes": [node("a"), node("b")]}
    rules = policy(["b", "a"], size=2)
    report = assert_success(case_dir, inventory, rules)
    assert report["schedule_risk"] == 0
    assert report["waves"][0]["unavailable_services"] == {}
    assert report["waves"][0]["cooldown_after"] == {}
    assert report["waves"][0]["rolling_unavailable"] == {}


def test_trailing_json_and_argument_count_are_invalid(case_dir):
    """Trailing JSON and both too few and too many paths use the exact invalid-input contract."""
    inventory_path = case_dir / "inventory.json"
    policy_path = case_dir / "policy.json"
    output_path = case_dir / "output.json"
    inventory_path.write_text('{"nodes":[]} {}', encoding="utf-8")
    inventory_path.chmod(0o644)
    write_json(policy_path, policy(["a"], size=1))
    for arguments in (
        [inventory_path, policy_path, output_path],
        [],
        [inventory_path, policy_path, output_path, "extra"],
    ):
        result = run_raw(arguments)
        assert result.returncode == 2
        assert result.stdout == b""
        assert result.stderr == b"drainwave: invalid input\n"


def test_io_errors_preserve_existing_output(case_dir):
    """Read and write failures use exit one and never replace an existing output."""
    inventory = {"nodes": [node("a")]}
    rules = policy(["a"], size=1)
    inventory_path = case_dir / "inventory.json"
    policy_path = case_dir / "policy.json"
    write_json(inventory_path, inventory)
    write_json(policy_path, rules)
    output_path = case_dir / "output.json"
    output_path.write_text("old", encoding="utf-8")
    output_path.chmod(0o666)
    missing = run_raw([case_dir / "missing.json", policy_path, output_path])
    assert missing.returncode == 1
    assert missing.stderr == b"drainwave: io error\n"
    assert output_path.read_text(encoding="utf-8") == "old"

    write_failure = run_raw([inventory_path, policy_path, "/proc/drainwave-verifier/plan.json"])
    assert write_failure.returncode == 1
    assert write_failure.stderr == b"drainwave: io error\n"


def test_repeated_runs_are_byte_deterministic(case_dir):
    """Identical complex inputs must produce byte-identical compact JSON on repeated atomic replacement."""
    inventory = {
        "nodes": [
            node("e", services=["api"]),
            node("d", services=["job"]),
            node("c", services=["api"]),
            node("b", services=["job"]),
            node("a", services=["api", "job"]),
            node("steady", "z2", "r2", 1, ["api", "job"]),
        ]
    }
    rules = policy(
        ["e", "d", "c", "b", "a"],
        cooldown={"api": 1},
        separations=[separation("a", "e", 1)],
        rolling_limits={"api": rolling(3, 2)},
        risk_weights={"api": 4, "job": 2},
        size=2,
    )
    _, _, first = invoke(case_dir, inventory, rules)
    _, _, second = invoke(case_dir, inventory, rules)
    assert first == second

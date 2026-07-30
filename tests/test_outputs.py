import ipaddress
import json
import random
import subprocess
from functools import cache
from pathlib import Path

BIN = "/app/bin/lockout-guard"


def op_key(op):
    return f"{op['op']}:{op.get('id', op.get('verdict'))}".encode()


def derived_operations(current, desired):
    current_by_id = {rule["id"]: rule for rule in current["rules"]}
    desired_by_id = {rule["id"]: rule for rule in desired["rules"]}
    operations = []
    for rule_id, rule in current_by_id.items():
        if rule_id not in desired_by_id:
            operations.append({"op": "delete", "id": rule_id})
        elif rule != desired_by_id[rule_id]:
            operations.append({"op": "replace", "id": rule_id})
    for rule_id in desired_by_id.keys() - current_by_id.keys():
        operations.append({"op": "add", "id": rule_id})
    if current["policy"] != desired["policy"]:
        operations.append({"op": "policy", "verdict": desired["policy"]})
    return sorted(operations, key=op_key)


def reference_plan(current, desired, probes):
    operations = derived_operations(current, desired)
    desired_by_id = {rule["id"]: rule for rule in desired["rules"]}

    @cache
    def state(mask):
        policy = current["policy"]
        rules = {rule["id"]: rule for rule in current["rules"]}
        for index, operation in enumerate(operations):
            if not mask & (1 << index):
                continue
            if operation["op"] == "policy":
                policy = operation["verdict"]
                continue
            rules.pop(operation["id"], None)
            if operation["op"] in {"add", "replace"}:
                rules[operation["id"]] = desired_by_id[operation["id"]]
        ordered = tuple(
            sorted(rules.values(), key=lambda rule: (rule["position"], rule["id"].encode()))
        )
        return policy, ordered

    @cache
    def safe(mask):
        policy, rules = state(mask)
        for probe in probes:
            verdict = policy
            address = ipaddress.ip_address(probe["source"])
            for rule in rules:
                port_matches = rule["port"] == 0 or rule["port"] == probe["port"]
                if port_matches and address in ipaddress.ip_network(rule["source"]):
                    verdict = rule["verdict"]
                    break
            if verdict != probe["must"]:
                return False
        return True

    if not safe(0):
        return {"operations": []}

    full = (1 << len(operations)) - 1
    initial_count = len(current["rules"])
    largest_count = initial_count + sum(op["op"] == "add" for op in operations)
    for peak in range(initial_count, largest_count + 1):

        @cache
        def reachable(mask, peak=peak):
            if mask == full:
                return True
            for index in range(len(operations)):
                bit = 1 << index
                if mask & bit:
                    continue
                next_mask = mask | bit
                if (
                    len(state(next_mask)[1]) <= peak
                    and safe(next_mask)
                    and reachable(next_mask)
                ):
                    return True
            return False

        if not reachable(0):
            continue
        answer = []
        mask = 0
        while mask != full:
            for index, operation in enumerate(operations):
                bit = 1 << index
                next_mask = mask | bit
                if (
                    not mask & bit
                    and len(state(next_mask)[1]) <= peak
                    and safe(next_mask)
                    and reachable(next_mask)
                ):
                    answer.append(operation)
                    mask = next_mask
                    break
        return {"operations": answer}
    return {"operations": []}


def run(tmp_path, current, desired, probes, *, timeout=8):
    paths = [tmp_path / name for name in ("c.json", "d.json", "p.json", "out.json")]
    for path, value in zip(paths[:3], (current, desired, probes), strict=True):
        path.write_text(json.dumps(value))
    completed = subprocess.run(
        [
            BIN,
            "--current",
            str(paths[0]),
            "--desired",
            str(paths[1]),
            "--probes",
            str(paths[2]),
            "--output",
            str(paths[3]),
        ],
        check=False,
        timeout=timeout,
    )
    assert completed.returncode == 0
    assert paths[3].is_file()
    return json.loads(paths[3].read_text())


def rule(rule_id, position, source, port, verdict):
    return {
        "id": rule_id,
        "position": position,
        "source": source,
        "port": port,
        "verdict": verdict,
    }


def test_public_defaults_renaming_and_input_order(tmp_path):
    values = [
        json.loads(Path(f"/app/task_file/{name}.json").read_text())
        for name in ("current", "desired", "probes")
    ]
    expected = {
        "operations": [
            {"op": "add", "id": "ssh-new"},
            {"op": "delete", "id": "ssh-old"},
        ]
    }
    assert run(tmp_path, *values) == expected

    default_output = Path("/app/out/plan.json")
    default_output.unlink(missing_ok=True)
    subprocess.run([BIN], check=True, timeout=8)
    assert json.loads(default_output.read_text()) == expected

    values[1]["rules"][0]["id"] = "mgmt-v2"
    values[0]["rules"].reverse()
    values[1]["rules"].reverse()
    assert run(tmp_path, *values) == reference_plan(*values)


def test_peak_minimization_beats_lexically_early_adds(tmp_path):
    current_rules = []
    desired_rules = []
    probes = []
    for index in range(5):
        address = f"10.40.{index}.7"
        network = f"10.40.{index}.0/24"
        current_rules.append(rule(f"old-{index}", 20, network, 22, "accept"))
        desired_rules.append(rule(f"new-{index}", 10, network, 22, "accept"))
        probes.append({"source": address, "port": 22, "must": "accept"})
    probes.append({"source": "203.0.113.8", "port": 22, "must": "drop"})
    current = {"policy": "drop", "rules": current_rules}
    desired = {"policy": "drop", "rules": desired_rules}
    expected = reference_plan(current, desired, probes)
    assert expected["operations"][1] == {"op": "delete", "id": "old-0"}
    assert run(tmp_path, current, desired, probes) == expected


def test_policy_fallback_and_any_port_require_non_greedy_order(tmp_path):
    current = {
        "policy": "drop",
        "rules": [
            rule("allow-old", 10, "10.8.0.0/16", 22, "accept"),
            rule("legacy-block", 20, "198.51.100.0/24", 8443, "drop"),
        ],
    }
    desired = {
        "policy": "accept",
        "rules": [rule("block-new", 5, "198.51.100.0/24", 0, "drop")],
    }
    probes = [
        {"source": "10.8.2.9", "port": 22, "must": "accept"},
        {"source": "198.51.100.9", "port": 443, "must": "drop"},
        {"source": "198.51.100.9", "port": 8443, "must": "drop"},
    ]
    assert run(tmp_path, current, desired, probes) == reference_plan(
        current, desired, probes
    )


def test_atomic_replacements_can_require_an_impossible_simultaneous_swap(tmp_path):
    current = {
        "policy": "drop",
        "rules": [
            rule("alpha", 10, "10.1.0.0/16", 22, "accept"),
            rule("beta", 10, "192.0.2.0/24", 22, "drop"),
            rule("x-fallback", 100, "10.1.0.0/16", 22, "drop"),
            rule("y-fallback", 100, "192.0.2.0/24", 22, "accept"),
        ],
    }
    desired = {
        "policy": "drop",
        "rules": [
            rule("alpha", 10, "192.0.2.0/24", 22, "drop"),
            rule("beta", 10, "10.1.0.0/16", 22, "accept"),
            rule("x-fallback", 100, "10.1.0.0/16", 22, "drop"),
            rule("y-fallback", 100, "192.0.2.0/24", 22, "accept"),
        ],
    }
    probes = [
        {"source": "10.1.9.9", "port": 22, "must": "accept"},
        {"source": "192.0.2.9", "port": 22, "must": "drop"},
    ]
    assert reference_plan(current, desired, probes) == {"operations": []}
    assert run(tmp_path, current, desired, probes) == {"operations": []}


def test_first_match_equal_positions_cidr_boundaries_and_initial_safety(tmp_path):
    current = {
        "policy": "drop",
        "rules": [
            rule("middle-accept", 10, "10.9.0.0/24", 443, "accept"),
            rule("z-last-drop", 20, "0.0.0.0/0", 443, "drop"),
        ],
    }
    desired = {
        "policy": "drop",
        "rules": [
            rule("a-first-accept", 20, "10.9.0.0/24", 443, "accept"),
            rule("z-last-drop", 20, "0.0.0.0/0", 443, "drop"),
        ],
    }
    probes = [
        {"source": "10.9.0.0", "port": 443, "must": "accept"},
        {"source": "10.9.0.255", "port": 443, "must": "accept"},
        {"source": "10.9.1.0", "port": 443, "must": "drop"},
    ]
    assert run(tmp_path, current, desired, probes) == reference_plan(
        current, desired, probes
    )

    unsafe_probes = probes + [
        {"source": "203.0.113.4", "port": 80, "must": "accept"}
    ]
    assert run(tmp_path, current, desired, unsafe_probes) == {"operations": []}


def test_deterministic_mutation_matrix(tmp_path):
    generator = random.Random(81173)
    for case_index in range(9):
        pair_count = generator.randint(1, 4)
        port = generator.choice([22, 53, 443, 9443])
        current_rules = []
        desired_rules = []
        probes = []
        for index in range(pair_count):
            second_octet = 60 + case_index
            network = f"10.{second_octet}.{index}.0/24"
            current_rules.append(
                rule(f"before-{case_index}-{index}", 30 + index, network, port, "accept")
            )
            desired_rules.append(
                rule(f"after-{case_index}-{index}", 10 + index, network, port, "accept")
            )
            probes.append(
                {
                    "source": f"10.{second_octet}.{index}.{generator.randint(1, 254)}",
                    "port": port,
                    "must": "accept",
                }
            )
        current_rules.append(rule(f"stable-{case_index}", 90, "0.0.0.0/0", 0, "drop"))
        desired_rules.append(rule(f"stable-{case_index}", 90, "0.0.0.0/0", 0, "drop"))
        generator.shuffle(current_rules)
        generator.shuffle(desired_rules)
        probes.append({"source": "203.0.113.77", "port": port, "must": "drop"})
        current = {"policy": "accept", "rules": current_rules}
        desired = {"policy": "accept", "rules": desired_rules}
        assert run(tmp_path, current, desired, probes) == reference_plan(
            current, desired, probes
        )


def test_twenty_operation_scalability_cliff(tmp_path):
    current_rules = []
    desired_rules = []
    probes = []
    expected_operations = []
    for index in range(10):
        network = f"172.20.{index}.0/24"
        current_rules.append(rule(f"old-{index:02}", 40, network, 22, "accept"))
        desired_rules.append(rule(f"new-{index:02}", 20, network, 22, "accept"))
        probes.append(
            {"source": f"172.20.{index}.17", "port": 22, "must": "accept"}
        )
        expected_operations.extend(
            [
                {"op": "add", "id": f"new-{index:02}"},
                {"op": "delete", "id": f"old-{index:02}"},
            ]
        )
    current = {"policy": "drop", "rules": current_rules}
    desired = {"policy": "drop", "rules": desired_rules}
    probes.append({"source": "172.31.0.1", "port": 22, "must": "drop"})
    assert run(tmp_path, current, desired, probes, timeout=10) == {
        "operations": expected_operations
    }


def test_no_changes(tmp_path):
    current = {
        "policy": "drop",
        "rules": [rule("same", 1, "0.0.0.0/0", 0, "drop")],
    }
    probes = [{"source": "192.0.2.1", "port": 65535, "must": "drop"}]
    assert run(tmp_path, current, current, probes) == {"operations": []}

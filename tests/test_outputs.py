"""Behavioral verifier for the confidential inference attestation planner."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path

import pytest


TASK_ROOT = Path(os.environ.get("TASK_FILE_DIR", "/app/task_file"))
PUBLIC = TASK_ROOT / "fixtures" / "public"
PUBLIC_HASHES = {
    "graph.json": "334ef268561593333a40f06411e7f0be1274df6132f90dabd8ef49c8f62612f4",
    "policy.json": "184bd86bfc7f79074e330d30d40878d6aa44691d8bd3d245f13d692bab0bb44e",
    "providers.json": "e841bbf35bdc9ce2871cb17cc607c530384a9e8d29f86cfbf854da74c2f1ade1",
}


def load_bundle(root: Path) -> tuple[dict, dict, dict]:
    return tuple(json.loads((root / name).read_text()) for name in ("graph.json", "providers.json", "policy.json"))


def write_bundle(root: Path, bundle: tuple[dict, dict, dict]) -> None:
    root.mkdir(parents=True)
    for name, value in zip(("graph.json", "providers.json", "policy.json"), bundle):
        (root / name).write_text(json.dumps(value, indent=2) + "\n")


def make_accessible(root: Path) -> None:
    """Allow the unprivileged candidate identity to traverse one fresh case tree."""
    root.mkdir(parents=True, exist_ok=True)
    current = root
    while current != Path("/tmp") and current != current.parent:
        current.chmod(current.stat().st_mode | 0o111)
        current = current.parent
    root.chmod(0o777)
    for path in root.rglob("*"):
        path.chmod(path.stat().st_mode | (0o055 if path.is_dir() else 0o044))


def run_candidate(binary: Path, args: list[str], cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run one candidate invocation with a private process group and sanitized identity."""
    make_accessible(cwd)
    process = subprocess.Popen(
        [str(binary), *args],
        cwd=str(cwd),
        env={"PATH": "/usr/local/go/bin:/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        user=65534,
        group=65534,
        extra_groups=[],
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def reference_plan(bundle: tuple[dict, dict, dict]) -> dict:
    graph, provider_doc, policy = copy.deepcopy(bundle)
    nodes, edges, providers = graph["nodes"], graph["edges"], provider_doc["providers"]
    node_pos = {node["id"]: i for i, node in enumerate(nodes)}
    rules = {rule["node_id"]: rule for rule in policy["placement_rules"]}
    transfers = {(row["from_provider"], row["to_provider"]): row for row in provider_doc["transfers"]}
    conversions = {(row["from_mode"], row["to_mode"]): row for row in provider_doc["conversions"]}
    incoming = [[] for _ in nodes]
    for edge_index, edge in enumerate(edges):
        incoming[node_pos[edge["to"]]].append(edge_index)

    group_of = [-1] * len(nodes)
    for group_index, group in enumerate(graph["enclave_groups"]):
        for node_id in group:
            group_of[node_pos[node_id]] = group_index

    candidates: list[list[dict]] = []
    for node in nodes:
        choices = []
        rule = rules.get(node["id"])
        for provider_index, provider in enumerate(providers):
            if provider["id"] not in policy["allowed_provider_ids"]:
                continue
            if provider["attestation_epoch"] < policy["minimum_attestation_epoch"]:
                continue
            if provider["trust_level"] < policy["minimum_trust"][node["classification"]]:
                continue
            if rule and provider["id"] not in rule["allowed_provider_ids"]:
                continue
            for capability in provider["capabilities"]:
                if capability["op"] != node["op"]:
                    continue
                for mode in capability["modes"]:
                    if rule and mode["name"] not in rule["allowed_modes"]:
                        continue
                    choices.append({"provider": provider_index, "mode": mode, "key": f'{provider["id"]}/{mode["name"]}'})
        candidates.append(sorted(choices, key=lambda choice: choice["key"]))

    suffix_min_latency = [0] * (len(nodes) + 1)
    suffix_min_memory = [0] * (len(nodes) + 1)
    for index in range(len(nodes) - 1, -1, -1):
        suffix_min_latency[index] = suffix_min_latency[index + 1]
        suffix_min_memory[index] = suffix_min_memory[index + 1]
        if candidates[index]:
            suffix_min_latency[index] += min(choice["mode"]["latency_us"] for choice in candidates[index])
            suffix_min_memory[index] += min(
                nodes[index]["output_bytes"] + choice["mode"]["workspace_bytes"]
                for choice in candidates[index]
            )

    chosen: list[dict | None] = [None] * len(nodes)
    path_exposure = [0] * len(nodes)
    memory = [0] * len(providers)
    key_use = [0] * len(providers)
    provider_use = [0] * len(providers)
    group_choice: list[str | None] = [None] * len(graph["enclave_groups"])
    boundary_rows: list[dict | None] = [None] * len(edges)
    best_key = None
    best_output = None

    def visit(index: int, node_latency: int, boundary_latency: int, transfer_count: int, conversion_count: int, encrypted_count: int, remote_count: int) -> None:
        nonlocal best_key, best_output
        if transfer_count > policy["max_transfers"] or conversion_count > policy["max_conversions"] or remote_count > policy["max_remote_nodes"]:
            return
        if best_key is not None:
            startup = sum(provider["startup_us"] for i, provider in enumerate(providers) if provider_use[i])
            lower_total = node_latency + boundary_latency + startup + suffix_min_latency[index]
            if any(not choices for choices in candidates[index:]):
                return
            lower_sequence = tuple(
                chosen[i]["key"] if i < index else candidates[i][0]["key"]
                for i in range(len(nodes))
            )
            total_minimum_memory = sum(memory) + suffix_min_memory[index]
            average_memory_lower_bound = (total_minimum_memory + len(providers) - 1) // len(providers)
            lower_objective = (
                lower_total,
                max(path_exposure[:index], default=0),
                max(max(memory, default=0), average_memory_lower_bound),
                max(key_use, default=0),
                transfer_count,
                conversion_count,
                lower_sequence,
            )
            if lower_objective >= best_key:
                return
        if index == len(nodes):
            startup = sum(provider["startup_us"] for i, provider in enumerate(providers) if provider_use[i])
            maximum_memory = max(memory, default=0)
            maximum_exposure = max(path_exposure, default=0)
            maximum_keys = max(key_use, default=0)
            total = node_latency + boundary_latency + startup
            sequence = tuple(choice["key"] for choice in chosen)
            objective = (total, maximum_exposure, maximum_memory, maximum_keys, transfer_count, conversion_count, sequence)
            if best_key is not None and objective >= best_key:
                return
            placements = [
                {"node_id": node["id"], "provider_id": providers[choice["provider"]]["id"], "mode": choice["mode"]["name"]}
                for node, choice in zip(nodes, chosen)
            ]
            best_key = objective
            best_output = {
                "workload_id": graph["workload_id"],
                "status": "ok",
                "placements": placements,
                "boundaries": copy.deepcopy(boundary_rows),
                "provider_resources": [
                    {"provider_id": provider["id"], "used_bytes": memory[i], "used_key_slots": key_use[i]}
                    for i, provider in enumerate(providers)
                ],
                "metrics": {
                    "node_latency_us": node_latency,
                    "boundary_latency_us": boundary_latency,
                    "startup_latency_us": startup,
                    "total_latency_us": total,
                    "path_exposure_ppm": maximum_exposure,
                    "max_provider_memory_bytes": maximum_memory,
                    "max_provider_key_slots_used": maximum_keys,
                    "transfer_count": transfer_count,
                    "conversion_count": conversion_count,
                    "encrypted_transfer_count": encrypted_count,
                    "remote_node_count": remote_count,
                },
            }
            return

        node = nodes[index]
        for choice in candidates[index]:
            group_index = group_of[index]
            newly_set_group = False
            if group_index >= 0:
                if group_choice[group_index] is not None and group_choice[group_index] != choice["key"]:
                    continue
                if group_choice[group_index] is None:
                    group_choice[group_index] = choice["key"]
                    newly_set_group = True

            provider_index = choice["provider"]
            added_memory = node["output_bytes"] + choice["mode"]["workspace_bytes"]
            if memory[provider_index] + added_memory > providers[provider_index]["memory_bytes"]:
                if newly_set_group:
                    group_choice[group_index] = None
                continue

            path_base = 0
            added_boundary_latency = 0
            added_transfers = 0
            added_conversions = 0
            added_encrypted = 0
            key_adds = [0] * len(providers)
            rows = []
            valid = True
            for edge_index in incoming[index]:
                edge = edges[edge_index]
                predecessor = chosen[node_pos[edge["from"]]]
                row = {"edge_id": edge["id"], "transfer": False, "conversion": False, "encrypted": False, "latency_us": 0, "exposure_ppm": 0}
                if predecessor["provider"] != provider_index:
                    transfer = transfers.get((providers[predecessor["provider"]]["id"], providers[provider_index]["id"]))
                    if transfer is None:
                        valid = False
                        break
                    row["transfer"] = True
                    if edge["sensitivity"] != "public" and not transfer["encrypted"]:
                        valid = False
                        break
                    row["encrypted"] = transfer["encrypted"]
                    row["latency_us"] += transfer["fixed_us"] + ((edge["tensor_bytes"] + 1023) // 1024) * transfer["per_kib_us"]
                    row["exposure_ppm"] += transfer["exposure_ppm"]
                    added_transfers += 1
                    if transfer["encrypted"]:
                        key_adds[predecessor["provider"]] += 1
                        key_adds[provider_index] += 1
                        added_encrypted += 1
                if predecessor["mode"]["name"] != choice["mode"]["name"]:
                    conversion = conversions.get((predecessor["mode"]["name"], choice["mode"]["name"]))
                    if conversion is None:
                        valid = False
                        break
                    row["conversion"] = True
                    row["latency_us"] += conversion["latency_us"]
                    row["exposure_ppm"] += conversion["exposure_ppm"]
                    added_conversions += 1
                path_base = max(path_base, path_exposure[node_pos[edge["from"]]] + row["exposure_ppm"])
                added_boundary_latency += row["latency_us"]
                rows.append((edge_index, row))

            if any(key_use[i] + key_adds[i] > provider["key_slots"] for i, provider in enumerate(providers)):
                valid = False
            current_path = path_base + choice["mode"]["exposure_ppm"]
            if not valid or current_path > policy["max_path_exposure_ppm"]:
                if newly_set_group:
                    group_choice[group_index] = None
                continue

            chosen[index] = choice
            path_exposure[index] = current_path
            memory[provider_index] += added_memory
            for i, added in enumerate(key_adds):
                key_use[i] += added
            provider_use[provider_index] += 1
            for edge_index, row in rows:
                boundary_rows[edge_index] = row
            visit(
                index + 1,
                node_latency + choice["mode"]["latency_us"],
                boundary_latency + added_boundary_latency,
                transfer_count + added_transfers,
                conversion_count + added_conversions,
                encrypted_count + added_encrypted,
                remote_count + int(providers[provider_index]["remote"]),
            )
            provider_use[provider_index] -= 1
            for i, added in enumerate(key_adds):
                key_use[i] -= added
            memory[provider_index] -= added_memory
            chosen[index] = None
            if newly_set_group:
                group_choice[group_index] = None

    visit(0, 0, 0, 0, 0, 0, 0)
    if best_output is None:
        return {"workload_id": graph["workload_id"], "status": "unsatisfied", "placements": [], "boundaries": [], "provider_resources": [], "metrics": None}
    return best_output


def synthetic_bundle(node_count: int = 6) -> tuple[dict, dict, dict]:
    nodes = [{"id": f"n{i}", "op": "Block", "classification": "restricted", "output_bytes": 120 + i * 7} for i in range(node_count)]
    edges = [{"id": f"e{i}", "from": f"n{i}", "to": f"n{i+1}", "sensitivity": "restricted", "tensor_bytes": 900 + i * 350} for i in range(node_count - 1)]
    graph = {"workload_id": f"synthetic-{node_count}", "nodes": nodes, "edges": edges, "enclave_groups": []}
    modes_a = [
        {"name": "fp32", "latency_us": 19, "workspace_bytes": 45, "exposure_ppm": 0},
        {"name": "fp16", "latency_us": 10, "workspace_bytes": 70, "exposure_ppm": 3},
    ]
    modes_b = [
        {"name": "fp32", "latency_us": 14, "workspace_bytes": 95, "exposure_ppm": 0},
        {"name": "fp16", "latency_us": 6, "workspace_bytes": 125, "exposure_ppm": 4},
    ]
    modes_r = [
        {"name": "fp16", "latency_us": 2, "workspace_bytes": 35, "exposure_ppm": 5},
    ]
    providers = {
        "providers": [
            {"id": "alpha", "memory_bytes": 1500, "startup_us": 5, "remote": False, "trust_level": 3, "attestation_epoch": 9, "key_slots": 6, "capabilities": [{"op": "Block", "modes": modes_a}]},
            {"id": "beta", "memory_bytes": 1500, "startup_us": 35, "remote": False, "trust_level": 2, "attestation_epoch": 9, "key_slots": 6, "capabilities": [{"op": "Block", "modes": modes_b}]},
            {"id": "remote", "memory_bytes": 2000, "startup_us": 20, "remote": True, "trust_level": 2, "attestation_epoch": 9, "key_slots": 4, "capabilities": [{"op": "Block", "modes": modes_r}]},
        ],
        "transfers": [],
        "conversions": [
            {"from_mode": "fp32", "to_mode": "fp16", "latency_us": 7, "exposure_ppm": 3},
            {"from_mode": "fp16", "to_mode": "fp32", "latency_us": 8, "exposure_ppm": 1},
        ],
    }
    for left in providers["providers"]:
        for right in providers["providers"]:
            if left["id"] != right["id"]:
                providers["transfers"].append({
                    "from_provider": left["id"], "to_provider": right["id"],
                    "fixed_us": 11 + (3 if "remote" in (left["id"], right["id"]) else 0),
                    "per_kib_us": 2, "exposure_ppm": 2, "encrypted": True,
                })
    policy = {
        "allowed_provider_ids": ["alpha", "beta", "remote"],
        "minimum_trust": {"public": 0, "restricted": 2, "secret": 3},
        "minimum_attestation_epoch": 8,
        "max_path_exposure_ppm": 28,
        "max_remote_nodes": 2,
        "max_transfers": 4,
        "max_conversions": 4,
        "placement_rules": [],
    }
    return graph, providers, policy


@pytest.fixture(scope="session")
def binary() -> Path:
    """Build the submitted Go command once for behavioral invocations."""
    target = Path(tempfile.mkdtemp(prefix="partitionplan-bin-")) / "partitionplan"
    subprocess.run(["go", "build", "-o", str(target), "./cmd/partitionplan"], cwd=TASK_ROOT, check=True, timeout=90)
    target.parent.chmod(0o755)
    target.chmod(0o755)
    return target


def invoke(binary: Path, bundle: tuple[dict, dict, dict], tmp_path: Path) -> dict:
    bundle_dir = tmp_path / "bundle"
    output = tmp_path / "nested" / "plan.json"
    write_bundle(bundle_dir, bundle)
    before = {path.name: path.read_bytes() for path in bundle_dir.iterdir()}
    completed = run_candidate(binary, [str(bundle_dir), str(output)], tmp_path)
    assert completed.returncode == 0, completed.stderr
    after = {path.name: path.read_bytes() for path in bundle_dir.iterdir()}
    assert after == before
    return json.loads(output.read_text())


def test_public_inputs_are_unchanged() -> None:
    """Protect the authoritative public graph, provider matrix, and policy fixtures."""
    for name, expected in PUBLIC_HASHES.items():
        assert hashlib.sha256((PUBLIC / name).read_bytes()).hexdigest() == expected


def test_candidate_identity_cannot_read_private_verifier(tmp_path: Path) -> None:
    """Confirm the candidate's runtime identity cannot inspect the private oracle."""
    make_accessible(tmp_path)
    probe = subprocess.run(
        ["/bin/sh", "-c", "test ! -r /tests/test_outputs.py"],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"},
        user=65534,
        group=65534,
        extra_groups=[],
        check=False,
    )
    assert probe.returncode == 0


def test_cli_contract_public_optimum_and_exact_schema(binary: Path, tmp_path: Path) -> None:
    """Verify argument handling, overwrite behavior, public correctness, ordering, and the documented schema."""
    assert run_candidate(binary, [], tmp_path / "no-args").returncode != 0
    assert run_candidate(binary, [str(PUBLIC)], tmp_path / "one-arg").returncode != 0
    assert run_candidate(binary, [str(PUBLIC), str(tmp_path / "unused.json"), "extra"], tmp_path / "extra-arg").returncode != 0
    output_path = tmp_path / "public-output" / "partition-plan.json"
    output_path.parent.mkdir()
    output_path.parent.chmod(0o777)
    output_path.write_text('{"stale":true}\n')
    output_path.chmod(0o666)
    completed = run_candidate(binary, [str(PUBLIC), str(output_path)], tmp_path)
    assert completed.returncode == 0, completed.stderr
    actual = json.loads(output_path.read_text())
    expected = reference_plan(load_bundle(PUBLIC))
    assert actual == expected
    assert set(actual) == {"workload_id", "status", "placements", "boundaries", "provider_resources", "metrics"}
    assert [row["node_id"] for row in actual["placements"]] == [row["id"] for row in load_bundle(PUBLIC)[0]["nodes"]]
    assert [row["edge_id"] for row in actual["boundaries"]] == [row["id"] for row in load_bundle(PUBLIC)[0]["edges"]]
    for name, expected_hash in PUBLIC_HASHES.items():
        assert hashlib.sha256((PUBLIC / name).read_bytes()).hexdigest() == expected_hash


def test_hidden_security_compatibility_matrix(binary: Path, tmp_path: Path) -> None:
    """Exercise trust, attestation, encryption, key capacity, ordering, resource, and enclave variations."""
    variants = []
    for variant_index in range(10):
        bundle = synthetic_bundle(5 + variant_index % 3)
        graph, providers, policy = bundle
        graph["workload_id"] = f"matrix-{variant_index}"
        if variant_index == 0:
            graph["enclave_groups"] = [["n1", "n2"]]
        elif variant_index == 1:
            graph["nodes"][2]["classification"] = "secret"
            policy["max_remote_nodes"] = 4
        elif variant_index == 2:
            providers["providers"][1]["memory_bytes"] = 480
        elif variant_index == 3:
            policy["max_path_exposure_ppm"] = 10
        elif variant_index == 4:
            policy["max_transfers"] = 0
            policy["max_conversions"] = 1
        elif variant_index == 5:
            policy["placement_rules"] = [{"node_id": "n3", "allowed_provider_ids": ["alpha"], "allowed_modes": ["fp32"]}]
        elif variant_index == 6:
            policy["allowed_provider_ids"] = ["beta", "alpha"]
        elif variant_index == 7:
            providers["providers"].reverse()
        elif variant_index == 8:
            providers["providers"][1]["attestation_epoch"] = 7
            providers["providers"][0]["key_slots"] = 1
        else:
            graph["edges"][1]["tensor_bytes"] = 4097
            graph["edges"][0]["sensitivity"] = "public"
            for transfer in providers["transfers"]:
                transfer["encrypted"] = False
        variants.append(bundle)
    for index, bundle in enumerate(variants):
        case_dir = tmp_path / f"case-{index}"
        assert invoke(binary, bundle, case_dir) == reference_plan(bundle)


def test_path_exposure_uses_predecessor_max_and_boundary_exposure(binary: Path, tmp_path: Path) -> None:
    """Distinguish path exposure from global summation across independent graph branches."""
    graph, providers, policy = synthetic_bundle(5)
    graph["workload_id"] = "branched-exposure"
    graph["edges"] = [
        {"id": "left", "from": "n0", "to": "n2", "sensitivity": "restricted", "tensor_bytes": 1025},
        {"id": "right", "from": "n1", "to": "n2", "sensitivity": "restricted", "tensor_bytes": 2048},
        {"id": "tail1", "from": "n2", "to": "n3", "sensitivity": "restricted", "tensor_bytes": 3073},
        {"id": "tail2", "from": "n3", "to": "n4", "sensitivity": "restricted", "tensor_bytes": 2048},
    ]
    policy["max_path_exposure_ppm"] = 14
    actual = invoke(binary, (graph, providers, policy), tmp_path)
    assert actual == reference_plan((graph, providers, policy))
    assert actual["metrics"]["path_exposure_ppm"] <= 14


def test_encrypted_boundaries_consume_endpoint_key_slots(binary: Path, tmp_path: Path) -> None:
    """Prove encrypted restricted-data crossings need capacity at both attested endpoints."""
    graph, providers, policy = synthetic_bundle(4)
    graph["workload_id"] = "endpoint-key-accounting"
    policy["max_remote_nodes"] = 0
    policy["max_transfers"] = 3
    policy["max_conversions"] = 0
    policy["placement_rules"] = [
        {"node_id": "n0", "allowed_provider_ids": ["alpha"], "allowed_modes": ["fp32"]},
        {"node_id": "n1", "allowed_provider_ids": ["beta"], "allowed_modes": ["fp32"]},
        {"node_id": "n2", "allowed_provider_ids": ["alpha"], "allowed_modes": ["fp32"]},
        {"node_id": "n3", "allowed_provider_ids": ["beta"], "allowed_modes": ["fp32"]},
    ]
    providers["providers"][0]["key_slots"] = 2
    providers["providers"][1]["key_slots"] = 2
    assert invoke(binary, (graph, providers, policy), tmp_path / "short") == {
        "workload_id": "endpoint-key-accounting", "status": "unsatisfied", "placements": [],
        "boundaries": [], "provider_resources": [], "metrics": None,
    }

    providers["providers"][0]["key_slots"] = 3
    providers["providers"][1]["key_slots"] = 3
    feasible = invoke(binary, (graph, providers, policy), tmp_path / "exact")
    assert feasible == reference_plan((graph, providers, policy))
    assert feasible["metrics"]["encrypted_transfer_count"] == 3
    assert feasible["metrics"]["max_provider_key_slots_used"] == 3

    for transfer in providers["transfers"]:
        if transfer["from_provider"] == "beta" and transfer["to_provider"] == "alpha":
            transfer["encrypted"] = False
    assert invoke(binary, (graph, providers, policy), tmp_path / "plaintext") == {
        "workload_id": "endpoint-key-accounting", "status": "unsatisfied", "placements": [],
        "boundaries": [], "provider_resources": [], "metrics": None,
    }


def test_unsatisfied_shape_for_security_constraint_conflict(binary: Path, tmp_path: Path) -> None:
    """Require the canonical empty result when enclave, trust, placement, and memory constraints conflict."""
    graph, providers, policy = synthetic_bundle(4)
    graph["workload_id"] = "unsatisfied-enclave"
    graph["enclave_groups"] = [["n0", "n1", "n2"]]
    graph["nodes"][0]["classification"] = "secret"
    providers["providers"][0]["memory_bytes"] = 200
    providers["providers"][1]["memory_bytes"] = 200
    policy["placement_rules"] = [{"node_id": "n1", "allowed_provider_ids": ["remote"], "allowed_modes": ["fp16"]}]
    actual = invoke(binary, (graph, providers, policy), tmp_path)
    assert actual == {
        "workload_id": "unsatisfied-enclave", "status": "unsatisfied", "placements": [],
        "boundaries": [], "provider_resources": [], "metrics": None,
    }


def test_complete_plan_tie_break_and_nonlocal_tradeoffs(binary: Path, tmp_path: Path) -> None:
    """Check full-sequence canonicalization when startup, memory, transfer, conversion, and local latency choices interact."""
    graph, providers, policy = synthetic_bundle(12)
    graph["workload_id"] = "coupled-tie-break"
    graph["enclave_groups"] = [["n2", "n3"], ["n7", "n8"]]
    providers["providers"][0]["memory_bytes"] = 1750
    providers["providers"][1]["memory_bytes"] = 1900
    policy["max_path_exposure_ppm"] = 24
    policy["max_remote_nodes"] = 0
    policy["max_transfers"] = 3
    policy["max_conversions"] = 3
    actual = invoke(binary, (graph, providers, policy), tmp_path)
    assert actual == reference_plan((graph, providers, policy))
    assert actual["status"] == "ok"


def test_maximum_size_search_with_coupled_budgets(binary: Path, tmp_path: Path) -> None:
    """Force exact optimization over maximum-size coupled and symmetry-heavy search spaces."""
    graph, providers, policy = synthetic_bundle(18)
    graph["workload_id"] = "maximum-coupled-search"
    providers["providers"][0]["memory_bytes"] = 3200
    providers["providers"][1]["memory_bytes"] = 3200
    providers["providers"][2]["memory_bytes"] = 4000
    policy["max_path_exposure_ppm"] = 45
    policy["max_remote_nodes"] = 3
    policy["max_transfers"] = 5
    policy["max_conversions"] = 5
    actual = invoke(binary, (graph, providers, policy), tmp_path)
    expected = reference_plan((graph, providers, policy))
    assert actual == expected
    assert actual["status"] == "ok"
    assert set(actual["metrics"]) == {
        "node_latency_us", "boundary_latency_us", "startup_latency_us", "total_latency_us",
        "path_exposure_ppm", "max_provider_memory_bytes", "max_provider_key_slots_used",
        "transfer_count", "conversion_count", "encrypted_transfer_count", "remote_node_count",
    }

    symmetric_graph = {
        "workload_id": "maximum-symmetric-search",
        "nodes": [
            {"id": f"s{i}", "op": "Unit", "classification": "public", "output_bytes": 1}
            for i in range(18)
        ],
        "edges": [],
        "enclave_groups": [[f"s{i}", f"s{i + 1}", f"s{i + 2}"] for i in range(0, 18, 3)],
    }
    symmetric_providers = {
        "providers": [
            {
                "id": provider_id,
                "memory_bytes": 100,
                "startup_us": 0,
                "remote": False,
                "trust_level": 0,
                "attestation_epoch": 1,
                "key_slots": 0,
                "capabilities": [{"op": "Unit", "modes": [
                    {"name": mode_name, "latency_us": 0, "workspace_bytes": 0, "exposure_ppm": 0}
                    for mode_name in mode_names
                ]}],
            }
            for provider_id, mode_names in (("alpha", ("m0", "m1")), ("beta", ("m0", "m1")), ("gamma", ("m0",)))
        ],
        "transfers": [],
        "conversions": [],
    }
    symmetric_policy = {
        "allowed_provider_ids": ["gamma", "beta", "alpha"],
        "minimum_trust": {"public": 0, "restricted": 1, "secret": 2},
        "minimum_attestation_epoch": 1,
        "max_path_exposure_ppm": 0,
        "max_remote_nodes": 0,
        "max_transfers": 0,
        "max_conversions": 0,
        "placement_rules": [],
    }
    symmetric_bundle = (symmetric_graph, symmetric_providers, symmetric_policy)
    symmetric_actual = invoke(binary, symmetric_bundle, tmp_path / "symmetric")
    assert symmetric_actual == reference_plan(symmetric_bundle)
    assert symmetric_actual["placements"] == [
        {
            "node_id": f"s{i}",
            "provider_id": "alpha" if i < 6 else "beta" if i < 12 else "gamma",
            "mode": "m0",
        }
        for i in range(18)
    ]


def test_compatible_bounds_unicode_tie_and_int64_values(binary: Path, tmp_path: Path) -> None:
    """Cover one-node graphs, one-to-four providers, Unicode ties, empty edges, and values beyond 32-bit range."""
    graph = {
        "workload_id": "bounds-and-unicode",
        "nodes": [{"id": "only", "op": "Unit", "classification": "public", "output_bytes": 4_294_967_300}],
        "edges": [],
        "enclave_groups": [],
    }
    mode = {"name": "fp32", "latency_us": 4_294_967_300, "workspace_bytes": 20, "exposure_ppm": 0}
    providers = {
        "providers": [
            {
                "id": provider_id,
                "memory_bytes": 5_000_000_000,
                "startup_us": 0,
                "remote": False,
                "trust_level": 3,
                "attestation_epoch": 9,
                "key_slots": 0,
                "capabilities": [{"op": "Unit", "modes": [copy.deepcopy(mode)]}],
            }
            for provider_id in ("βeta", "éclair", "zeta", "alpha")
        ],
        "transfers": [],
        "conversions": [],
    }
    policy = {
        "allowed_provider_ids": ["éclair", "zeta", "βeta", "alpha"],
        "minimum_trust": {"public": 0, "restricted": 2, "secret": 3},
        "minimum_attestation_epoch": 8,
        "max_path_exposure_ppm": 0,
        "max_remote_nodes": 0,
        "max_transfers": 0,
        "max_conversions": 0,
        "placement_rules": [],
    }
    four_provider_bundle = (graph, providers, policy)
    actual = invoke(binary, four_provider_bundle, tmp_path / "four")
    assert actual == reference_plan(four_provider_bundle)
    assert actual["placements"] == [{"node_id": "only", "provider_id": "alpha", "mode": "fp32"}]
    assert actual["boundaries"] == []
    assert actual["metrics"]["total_latency_us"] == 4_294_967_300

    one_provider_graph = copy.deepcopy(graph)
    one_provider_graph["workload_id"] = "one-provider-bound"
    one_provider_doc = copy.deepcopy(providers)
    one_provider_doc["providers"] = [one_provider_doc["providers"][0]]
    one_provider_doc["providers"][0]["capabilities"][0]["modes"] = [
        {**copy.deepcopy(mode), "name": "zmode"},
        {**copy.deepcopy(mode), "name": "amode"},
    ]
    one_provider_policy = copy.deepcopy(policy)
    one_provider_policy["allowed_provider_ids"] = ["βeta"]
    one_provider_policy["placement_rules"] = [
        {"node_id": "only", "allowed_provider_ids": ["βeta"], "allowed_modes": ["zmode", "amode"]}
    ]
    one_provider_bundle = (one_provider_graph, one_provider_doc, one_provider_policy)
    one_provider_actual = invoke(binary, one_provider_bundle, tmp_path / "one")
    assert one_provider_actual == reference_plan(one_provider_bundle)
    assert one_provider_actual["placements"] == [{"node_id": "only", "provider_id": "βeta", "mode": "amode"}]


def test_transfer_ceiling_is_safe_at_signed_int64_limit(binary: Path, tmp_path: Path) -> None:
    """Require overflow-safe KiB ceiling arithmetic for the documented signed-64-bit domain."""
    maximum_int64 = (1 << 63) - 1
    graph = {
        "workload_id": "int64-transfer-ceiling",
        "nodes": [
            {"id": "source", "op": "Block", "classification": "restricted", "output_bytes": 1},
            {"id": "sink", "op": "Block", "classification": "restricted", "output_bytes": 1},
        ],
        "edges": [
            {
                "id": "large-tensor",
                "from": "source",
                "to": "sink",
                "sensitivity": "restricted",
                "tensor_bytes": maximum_int64,
            }
        ],
        "enclave_groups": [],
    }
    mode = {"name": "exact", "latency_us": 0, "workspace_bytes": 0, "exposure_ppm": 0}
    providers = {
        "providers": [
            {
                "id": provider_id,
                "memory_bytes": 10,
                "startup_us": 0,
                "remote": False,
                "trust_level": 2,
                "attestation_epoch": 1,
                "key_slots": 1,
                "capabilities": [{"op": "Block", "modes": [copy.deepcopy(mode)]}],
            }
            for provider_id in ("left", "right")
        ],
        "transfers": [
            {
                "from_provider": "left",
                "to_provider": "right",
                "encrypted": True,
                "fixed_us": 0,
                "per_kib_us": 1,
                "exposure_ppm": 0,
            }
        ],
        "conversions": [],
    }
    policy = {
        "allowed_provider_ids": ["left", "right"],
        "minimum_trust": {"public": 0, "restricted": 2, "secret": 3},
        "minimum_attestation_epoch": 1,
        "max_path_exposure_ppm": 0,
        "max_remote_nodes": 0,
        "max_transfers": 1,
        "max_conversions": 0,
        "placement_rules": [
            {"node_id": "source", "allowed_provider_ids": ["left"], "allowed_modes": ["exact"]},
            {"node_id": "sink", "allowed_provider_ids": ["right"], "allowed_modes": ["exact"]},
        ],
    }
    bundle = (graph, providers, policy)
    actual = invoke(binary, bundle, tmp_path)
    expected_ceiling = maximum_int64 // 1024 + 1
    assert actual == reference_plan(bundle)
    assert actual["boundaries"][0]["latency_us"] == expected_ceiling
    assert actual["metrics"]["boundary_latency_us"] == expected_ceiling

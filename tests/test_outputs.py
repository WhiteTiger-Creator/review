#!/usr/bin/env python3
"""Verifier for WireGuard peer mesh reconciliation plan output."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
from collections import defaultdict
from pathlib import Path

INVENTORY = Path("/app/inventory")
OUTPUT = Path("/app/output/mesh_plan.json")
CONTRACT = Path("/app/docs/mesh-ops-policy.md")
PROFILE = Path("/app/config/profiles/mesh-core/ops.toml")
PROFILE_NAME = Path("/app/config/profile.name")

T0 = 1720000000
GRACE = 1800
RUN_ID = "wireguard-peer-mesh-v1"
KEEPALIVE_FLOOR = 15
CORRECT_SEAL = "5f0a62ba49ac1be3f92f94c519f278948327d68894b341dd884124e1894c6d21"

INVENTORY_SHA256 = {
    "endpoints/e01.json": "5323bd6d159e048be4fbafcc09f4e680e1210c963e2704350eae9d3e747b2dbb",
    "meshes/m01.json": "05796e3379203ef1d92aa6d4c25d2cb8acc1f6547c31c3f02fd4f8d4d4d383fd",
    "peers/p01.json": "b133dc92a8d0cf41e26d9c25c94f09b50cf34256a46054461103b0e37cbdf2e6",
    "peers/p02.json": "ef4453e3b9f489ec1c77599b798e5556390c8b15732831fd7202fcae3d161c5e",
    "peers/p03.json": "ebf8b3a953989442b86e88e7188105f1489e4079b390767fd075eeb30df5907b",
    "peers/p04.json": "a84b0e3ee6d33f4befdb46e6ec4bc7e88e6858539f59f84bab0daad5293cf912",
    "peers/p05.json": "f776eb779dbbf5b8d44660cf16cfa4b3914b2002297d418ec62044da3b65a65d",
    "peers/p06.json": "21bc33790aec553462d3fd08b526145474e17d2d69f95cd7d7ae8eedc4cf1e13",
    "peers/p07.json": "f1a829485ab90e58a06e69c5248b13ec15e6af2b51ab0c0bb1ae12a40aedb20e",
    "peers/p08.json": "0b091ab8ad925e1ba924f8f0c82212c787614d95e763fe53d88f590eb9bf64a0",
    "peers/p09.json": "92c6992e35a31aa38da1e7028985736f65bd548234e9d8e94c2c1cf5f9de3d54",
    "peers/p10.json": "30f7664645f14ae587ccf439bf363f16e27891ca8b654636284483f6ea18c36f",
    "peers/p11.json": "ba1ad727288cb2b978909eab6245b161c81e5367e9fbde1251072ff1294447bb",
    "peers/p12.json": "56e55261945eb6a1c1c604d03dc86c1f0d5c7c6103948fb3eed321cdc5bd1965",
    "peers/p13.json": "405dfa588ae1712d0949b82ae88ad1ed77d39e7e8aac17e4725c30dd13582ced",
    "peers/p14.json": "ea10748fc52a9ea9526303ae718c58cbafba79905b2d6dacfa92a1b88515f627",
    "peers/p15.json": "5837c588fe2f46f405ae329712f2215d69b2e101c31669fcc2f87922a257a14f",
    "peers/p16.json": "dca7fb3da4a09d5761f0103e7e7d7f29203012ad4b35649b6d7e5533cb6aa30d",
    "peers/p17.json": "c18f3d04cd58fae4a0bccf41876d8b376bc4aafe8eb4313a421538626973971f",
    "peers/p18.json": "d682f88beb1558220968987ba9bf73b2966c1c043d57447c5d786c07cddbe5e1",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _half_away_round(x: float) -> int:
    """Match Go math.Round (half away from zero)."""
    if x >= 0:
        return math.floor(x + 0.5)
    return math.ceil(x - 0.5)


def _config_seal(
    grace: int,
    allow_disabled: bool,
    soft_conflict: bool,
    prefer_keepalive: bool,
    dual_iface: bool,
) -> str:
    payload = (
        f"run_id={RUN_ID}\n"
        f"ops_epoch={T0}\n"
        f"handshake_grace_sec={grace}\n"
        f"allow_disabled={'true' if allow_disabled else 'false'}\n"
        f"soft_peer_conflict={'true' if soft_conflict else 'false'}\n"
        f"prefer_keepalive={'true' if prefer_keepalive else 'false'}\n"
        f"dual_iface_link={'true' if dual_iface else 'false'}\n"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _load_corpus():
    meshes = {
        n["mesh_id"]: n
        for n in json.loads((INVENTORY / "meshes" / "m01.json").read_text())["nets"]
    }
    endpoints = json.loads((INVENTORY / "endpoints" / "e01.json").read_text())[
        "endpoints"
    ]
    peers = []
    for path in sorted((INVENTORY / "peers").glob("*.json")):
        peers.append(json.loads(path.read_text()))
    return meshes, endpoints, peers


def _in_mesh(ip: str, mesh_id: str, meshes: dict) -> bool:
    return ipaddress.ip_address(ip) in ipaddress.ip_network(
        meshes[mesh_id]["cidr"], strict=False
    )


def _find_ep(pk: str, iface: str, endpoints: list):
    if not pk:
        return None
    for e in endpoints:
        if e["iface"] == iface and e["public_key"] == pk:
            return e
    return None


def _score(classification: str, reasons: list[str]) -> tuple[str, int]:
    base = {
        "keep": ("none", 0),
        "reclaim": ("low", 30),
        "reassign": ("medium", 60),
        "endpoint_bind": ("high", 76),
        "keepalive_bind": ("high", 76),
        "reject": ("high", 84),
    }[classification]
    sev, sc = base
    if classification == "reject" and "out_of_mesh" in reasons:
        sev, sc = "critical", 95
    elif classification == "reject" and "disabled_forbidden" in reasons:
        sev, sc = "critical", 89
    if "peer_cross_mesh" in reasons and classification == "keep":
        sev, sc = "high", 71
    return sev, sc


def _expected_report():
    meshes, endpoints, peers = _load_corpus()
    raw = []
    for peer in peers:
        ra = {
            "peer_id": peer["peer_id"],
            "mesh_id": peer["mesh_id"],
            "public_key": peer["public_key"],
            "endpoint": peer["endpoint"],
            "allowed_ip": peer["allowed_ip"],
            "iface": peer["iface"],
            "last_handshake": peer["last_handshake"],
            "keepalive_sec": peer["keepalive_sec"],
        }
        if not _in_mesh(peer["allowed_ip"], peer["mesh_id"], meshes):
            ra["classification"] = "reject"
            ra["reasons"] = ["out_of_mesh"]
        elif peer["state"] == "disabled":
            ra["classification"] = "reject"
            ra["reasons"] = ["disabled_forbidden"]
        else:
            ep = _find_ep(peer["public_key"], peer["iface"], endpoints)
            if ep is not None and peer["endpoint"] != ep["endpoint"]:
                ra["classification"] = "endpoint_bind"
                ra["reasons"] = ["endpoint_mismatch"]
            elif peer["keepalive_sec"] < KEEPALIVE_FLOOR:
                ra["classification"] = "keepalive_bind"
                ra["reasons"] = ["keepalive_policy"]
            elif peer["last_handshake"] + GRACE < T0:
                ra["classification"] = "reclaim"
                ra["reasons"] = ["stale_handshake"]
            else:
                ra["classification"] = "keep"
                ra["reasons"] = ["peer_authoritative"]
        raw.append(ra)

    by_ip: dict[str, list[int]] = defaultdict(list)
    for i, ra in enumerate(raw):
        if ra["classification"] in ("keep", "endpoint_bind", "keepalive_bind"):
            by_ip[ra["allowed_ip"]].append(i)

    for idxs in by_ip.values():
        if len(idxs) <= 1:
            continue
        winner = idxs[0]
        for i in idxs[1:]:
            a, b = raw[i], raw[winner]
            better = a["last_handshake"] > b["last_handshake"] or (
                a["last_handshake"] == b["last_handshake"]
                and a["peer_id"] < b["peer_id"]
            )
            if better:
                winner = i
        for i in idxs:
            if i == winner:
                continue
            raw[i]["classification"] = "reassign"
            raw[i]["reasons"] = ["allowedip_conflict_loss"]

    for i, ra in enumerate(raw):
        rel: list[str] = []
        for j, rb in enumerate(raw):
            if i == j:
                continue
            if ra["public_key"] == rb["public_key"] and ra["iface"] != rb["iface"]:
                rel.append(rb["peer_id"])
        if ra["classification"] == "keep" and ra["public_key"]:
            cross = False
            for j, rb in enumerate(raw):
                if i == j:
                    continue
                if (
                    rb["classification"] == "keep"
                    and rb["public_key"] == ra["public_key"]
                    and rb["mesh_id"] != ra["mesh_id"]
                ):
                    rel.append(rb["peer_id"])
                    cross = True
            if cross and "peer_cross_mesh" not in ra["reasons"]:
                ra["reasons"] = list(ra["reasons"]) + ["peer_cross_mesh"]
        ra["related_ids"] = sorted(set(rel))

    actions = []
    for ra in sorted(raw, key=lambda x: x["peer_id"]):
        sev, sc = _score(ra["classification"], ra["reasons"])
        actions.append(
            {
                "peer_id": ra["peer_id"],
                "mesh_id": ra["mesh_id"],
                "public_key": ra["public_key"],
                "endpoint": ra["endpoint"],
                "allowed_ip": ra["allowed_ip"],
                "iface": ra["iface"],
                "classification": ra["classification"],
                "severity": sev,
                "priority_score": sc,
                "reasons": ra["reasons"],
                "related_ids": ra["related_ids"],
            }
        )

    counts = {
        "keep_count": 0,
        "reclaim_count": 0,
        "reassign_count": 0,
        "reject_count": 0,
        "endpoint_bind_count": 0,
        "keepalive_bind_count": 0,
    }
    rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    max_sev = "none"
    total = 0
    for a in actions:
        key = a["classification"] + "_count"
        counts[key] += 1
        total += a["priority_score"]
        if rank[a["severity"]] > rank[max_sev]:
            max_sev = a["severity"]

    agg = min(100, _half_away_round(total / len(actions) * 1.35))
    return {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "ops_epoch": T0,
        "peers_analyzed": len(actions),
        "actions": actions,
        "summary": {
            **counts,
            "max_severity": max_sev,
            "aggregate_priority": agg,
        },
    }


def test_contract_and_profile_present():
    """Ops policy and sealed mesh-core profile files must exist for ops resolution."""
    assert CONTRACT.is_file()
    assert PROFILE.is_file()
    assert PROFILE_NAME.read_text().strip() == "mesh-core"


def test_inventory_not_modified():
    """Inventory JSON inputs must remain unmodified (anti-cheating pin)."""
    for rel, digest in INVENTORY_SHA256.items():
        assert _sha256(INVENTORY / rel) == digest, rel


def test_sealed_profile_matches_contract():
    """Active mesh-core ops.toml must use spaced TOML floors and matching seal."""
    text = PROFILE.read_text()
    assert 'run_id = "wireguard-peer-mesh-v1"' in text
    assert "ops_epoch = 1720000000" in text
    assert "handshake_grace_sec = 1800" in text
    assert "allow_disabled = false" in text
    assert "soft_peer_conflict = false" in text
    assert "prefer_keepalive = true" in text
    assert "dual_iface_link = true" in text
    assert f'config_seal = "{CORRECT_SEAL}"' in text
    assert CORRECT_SEAL == _config_seal(1800, False, False, True, True)


def test_seal_mismatch_uses_compliant_baseline():
    """Seal mismatch must still apply ops floors via runtime baseline (behavior, not source names)."""
    import subprocess

    backup = PROFILE.read_text()
    out_dir = Path("/tmp/wg-baseline-out")
    try:
        PROFILE.write_text(backup.replace(CORRECT_SEAL, "0" * 64))
        out_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [
                "/app/bin/wgmeshd",
                "--inventory",
                "/app/inventory",
                "--config",
                "/app/config",
                "--out",
                str(out_dir),
            ],
            cwd="/app",
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        plan = json.loads((out_dir / "mesh_plan.json").read_text())
        by = {a["peer_id"]: a for a in plan["actions"]}
        assert by["p03"]["classification"] == "reject"
        assert by["p03"]["reasons"] == ["disabled_forbidden"]
        assert by["p06"]["classification"] == "reclaim"
        assert by["p05"]["classification"] == "keepalive_bind"
        assert by["p01"]["related_ids"] == ["p11"]
        assert plan["summary"]["endpoint_bind_count"] == 2
        assert plan["summary"]["keepalive_bind_count"] == 2
        assert plan["summary"]["aggregate_priority"] == 68
    finally:
        PROFILE.write_text(backup)


def test_legacy_profile_tree_not_authoritative():
    """When WG_PROFILE_ROOT is unset, corrupting profiles.legacy must not change the plan."""
    import os
    import subprocess

    legacy = Path("/app/config/profiles.legacy/mesh-core/ops.toml")
    backup = legacy.read_text() if legacy.is_file() else None
    out_dir = Path("/tmp/wg-legacy-out")
    try:
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            'run_id = "legacy-shadow"\n'
            "ops_epoch = 1\n"
            "handshake_grace_sec = 1\n"
            "allow_disabled = true\n"
            "soft_peer_conflict = true\n"
            "prefer_keepalive = false\n"
            "dual_iface_link = false\n"
            'config_seal = "00"\n'
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items() if k != "WG_PROFILE_ROOT"}
        proc = subprocess.run(
            [
                "/app/bin/wgmeshd",
                "--inventory",
                "/app/inventory",
                "--config",
                "/app/config",
                "--out",
                str(out_dir),
            ],
            cwd="/app",
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert proc.returncode == 0, proc.stderr
        plan = json.loads((out_dir / "mesh_plan.json").read_text())
        expected = _expected_report()
        assert plan["summary"] == expected["summary"]
        by = {a["peer_id"]: a for a in plan["actions"]}
        assert by["p08"]["classification"] == "keep"
        assert by["p07"]["classification"] == "reassign"
        assert "peer_cross_mesh" in by["p01"]["reasons"]
    finally:
        if backup is None:
            if legacy.is_file():
                legacy.unlink()
        else:
            legacy.write_text(backup)


def test_plan_schema_and_sorting():
    """mesh_plan.json must exist with required fields, sorted actions, and empty related_ids as []."""
    assert OUTPUT.is_file()
    raw = OUTPUT.read_text()
    assert '"related_ids": null' not in raw
    plan = json.loads(raw)
    for key in (
        "schema_version",
        "run_id",
        "ops_epoch",
        "peers_analyzed",
        "actions",
        "summary",
    ):
        assert key in plan
    assert plan["schema_version"] == "1.0"
    ids = [a["peer_id"] for a in plan["actions"]]
    assert ids == sorted(ids)
    for a in plan["actions"]:
        assert isinstance(a["related_ids"], list)
        assert a["related_ids"] == sorted(a["related_ids"])
    by = {a["peer_id"]: a for a in plan["actions"]}
    assert by["p02"]["related_ids"] == []
    assert by["p09"]["related_ids"] == []


def test_plan_matches_ops_expectations():
    """Full plan must match independently recomputed ops-policy expectations."""
    expected = _expected_report()
    plan = json.loads(OUTPUT.read_text())
    assert plan["run_id"] == expected["run_id"]
    assert plan["ops_epoch"] == expected["ops_epoch"]
    assert plan["peers_analyzed"] == expected["peers_analyzed"]
    assert len(plan["actions"]) == len(expected["actions"])
    for got, exp in zip(plan["actions"], expected["actions"], strict=True):
        assert got == exp, got["peer_id"]
    assert plan["summary"] == expected["summary"]


def test_out_of_mesh_and_disabled_rejects():
    """Out-of-mesh and disabled peers must reject with critical severities."""
    plan = json.loads(OUTPUT.read_text())
    by = {a["peer_id"]: a for a in plan["actions"]}
    assert by["p02"]["classification"] == "reject"
    assert by["p02"]["reasons"] == ["out_of_mesh"]
    assert by["p02"]["priority_score"] == 95
    assert by["p03"]["classification"] == "reject"
    assert by["p03"]["reasons"] == ["disabled_forbidden"]
    assert by["p03"]["priority_score"] == 89
    assert by["p10"]["reasons"] == ["out_of_mesh"]


def test_endpoint_keepalive_and_conflict_winners():
    """Endpoint/keepalive binds fire; newest handshake wins AllowedIP conflicts."""
    plan = json.loads(OUTPUT.read_text())
    by = {a["peer_id"]: a for a in plan["actions"]}
    assert by["p04"]["classification"] == "endpoint_bind"
    assert by["p13"]["classification"] == "endpoint_bind"
    assert by["p05"]["classification"] == "keepalive_bind"
    assert by["p14"]["classification"] == "keepalive_bind"
    assert by["p08"]["classification"] == "keep"
    assert by["p07"]["classification"] == "reassign"
    assert by["p09"]["classification"] == "keep"
    assert by["p09"]["priority_score"] == 0
    assert by["p18"]["classification"] == "keep"
    assert by["p17"]["classification"] == "reassign"
    assert by["p15"]["classification"] == "keep"


def test_stale_reclaim_and_grace_boundary():
    """Stale reclaim uses grace window; within-grace handshake stays keep."""
    plan = json.loads(OUTPUT.read_text())
    by = {a["peer_id"]: a for a in plan["actions"]}
    assert by["p06"]["classification"] == "reclaim"
    assert by["p16"]["classification"] == "reclaim"
    assert by["p12"]["classification"] == "keep"


def test_dual_iface_and_cross_mesh_related():
    """Dual-iface pubkey links and cross-mesh escalation must appear."""
    plan = json.loads(OUTPUT.read_text())
    by = {a["peer_id"]: a for a in plan["actions"]}
    assert by["p01"]["related_ids"] == ["p11"]
    assert by["p11"]["related_ids"] == ["p01"]
    assert "peer_cross_mesh" in by["p01"]["reasons"]
    assert "peer_cross_mesh" in by["p11"]["reasons"]
    assert by["p01"]["priority_score"] == 71
    assert by["p11"]["priority_score"] == 71


def test_aggregate_priority_formula():
    """aggregate_priority must equal min(100, round(mean * 1.35))."""
    plan = json.loads(OUTPUT.read_text())
    scores = [a["priority_score"] for a in plan["actions"]]
    expected = min(100, _half_away_round(sum(scores) / len(scores) * 1.35))
    assert plan["summary"]["aggregate_priority"] == expected
    assert plan["summary"]["max_severity"] == "critical"
    assert plan["summary"]["reject_count"] == 3
    assert plan["summary"]["endpoint_bind_count"] == 2
    assert plan["summary"]["keepalive_bind_count"] == 2
    assert plan["summary"]["reassign_count"] == 2

"""Verifier for edge fleet trust attestation recovery."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

OUTPUT = Path("/output/ceremony-ledger.json")
QUARANTINE = Path("/output/quarantine.json")
FIXTURES = Path("/app/data/fixtures")
SURFACE = FIXTURES / "surface_attestation.json"
SEED = FIXTURES / "seed.json"
SEGMENTS = Path("/app/data/signed_segments")
VERIFIER_OUT = Path("/tmp") / "ceremony-ledger-verify.json"
DYNAMIC_OUT = Path("/tmp") / "ceremony-ledger-dynamic.json"
DYNAMIC_FRAME = FIXTURES / "dynamic_test_frame.bin"
DYNAMIC_INJECTED = FIXTURES / "dynamic_test_injected.bin"

EPOCH_10_ACCEPTED = 8
EPOCH_20_ACCEPTED = 5
EPOCH_30_ACCEPTED = 3
EPOCH_40_ACCEPTED = 5
EPOCH_50_ACCEPTED = 4
SURFACE_EPOCH_10 = 10
SCHEMA_VERSION = 1
STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"
PROFILE_A = "fleet_a"
PROFILE_B = "fleet_b"
BACKEND_NAMES = {"mqtt", "lora", "uart", "canbus", "zigbee"}
PUBLISHED_EPOCHS = {10, 20, 30, 40, 50}
CORE_EPOCHS = {10, 20, 40, 50}
REASON_INTEGRITY = "integrity_failure"
REASON_REPLAY = "replay"
REASON_REVOKED = "revoked"
QUARANTINE_REASONS = (REASON_INTEGRITY, REASON_REPLAY, REASON_REVOKED)
KEY_BACKENDS = "backends"
KEY_EPOCHS = "epochs"
KEY_REJECTED = "rejected"
KEY_EPOCH = "epoch"
KEY_LANE = "lane"
KEY_TS = "ts"
EPOCH_TEN = 10
EPOCH_THIRTY = 30
EPOCH_TWENTY_FIVE = 25
BAND_LO = 2
BAND_HI = 4
BAND_CAP = 6
BACKEND_COUNT = 5
SAMPLE_A = "sample_a"
SAMPLE_B = "sample_b"
SAMPLE_C = "sample_c"
SEED_NAME = "lane-lattice-v2"
DYNAMIC_LEGACY = FIXTURES / "dynamic_test_legacy.bin"


def _quarantine_path_for(attest_out: Path) -> Path:
    name = attest_out.name.replace("ceremony-ledger", "quarantine")
    return attest_out.with_name(name)


def _rebuild_and_attest(out: Path) -> dict:
    result = subprocess.run(
        ["cargo", "build", "-p", "trusteval", "--release"],
        cwd="/app",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"cargo build failed:\n{result.stderr}"
    result = subprocess.run(
        ["/app/target/release/trusteval", "attest", "--out", str(out)],
        cwd="/app",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"trusteval attest failed:\n{result.stderr}"
    body = out.read_text(encoding="utf-8")
    data = json.loads(body)
    assert data.get("version") == SCHEMA_VERSION
    return data


def _load_quarantine(path: Path) -> dict:
    assert path.is_file(), f"missing quarantine at {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("version") == SCHEMA_VERSION
    assert KEY_REJECTED in data
    return data


def _reason_keys(data: dict, reason: str) -> set[tuple]:
    return {
        (int(e["epoch"]), e["lane"], int(e["ts"]))
        for e in data["rejected"]
        if e["reason"] == reason
    }


@pytest.fixture(scope="module")
def roster_from_binary() -> dict:
    """Fresh rebuild + attestation from current /app sources."""
    return _rebuild_and_attest(VERIFIER_OUT)


@pytest.fixture(scope="module")
def quarantine_from_binary(roster_from_binary: dict) -> dict:
    """Quarantine produced by the same rebuild as roster_from_binary."""
    _ = roster_from_binary
    return _load_quarantine(_quarantine_path_for(VERIFIER_OUT))


def _status_map(roster: dict) -> dict[str, str]:
    assert roster.get("version") == SCHEMA_VERSION
    backends = roster["backends"]
    return {row["name"]: row["status"] for row in backends}


def _epoch_map(roster: dict) -> dict[int, dict]:
    return {int(row["id"]): row for row in roster["epochs"]}


def test_roster_structure(roster_from_binary: dict):
    """Attestation shape plus deep-path signal (not surface-inflated epoch 10)."""
    assert roster_from_binary["version"] == SCHEMA_VERSION
    assert KEY_BACKENDS in roster_from_binary
    assert KEY_EPOCHS in roster_from_binary
    backends = roster_from_binary["backends"]
    assert len(backends) == BACKEND_COUNT
    names = {b["name"] for b in backends}
    assert names == BACKEND_NAMES
    for b in backends:
        assert b["status"] in (STATUS_ACTIVE, STATUS_INACTIVE)
    epochs = _epoch_map(roster_from_binary)
    assert CORE_EPOCHS.issubset(epochs.keys())
    assert int(epochs[EPOCH_TEN]["accepted"]) < SURFACE_EPOCH_10
    assert int(epochs[EPOCH_TEN]["accepted"]) >= EPOCH_30_ACCEPTED


def test_authority_correct_tier(roster_from_binary: dict):
    """Epoch 10 accepted count matches restored deep attestation."""
    epochs = _epoch_map(roster_from_binary)
    assert EPOCH_TEN in epochs
    accepted_10 = int(epochs[EPOCH_TEN]["accepted"])
    assert accepted_10 == EPOCH_10_ACCEPTED


def test_keyed_integrity_rejects_injected(roster_from_binary: dict):
    """Forged frames must not inflate epoch 10 accepted."""
    epochs = _epoch_map(roster_from_binary)
    assert int(epochs[EPOCH_TEN]["accepted"]) == EPOCH_10_ACCEPTED
    assert int(epochs[EPOCH_TEN]["accepted"]) < SURFACE_EPOCH_10


def test_keyed_integrity_epoch30(roster_from_binary: dict):
    """Epoch 30 remains published under hold co-presence with reduced tally."""
    epochs = _epoch_map(roster_from_binary)
    assert EPOCH_THIRTY in epochs
    accepted = int(epochs[EPOCH_THIRTY]["accepted"])
    assert BAND_LO <= accepted <= BAND_HI
    assert accepted < BAND_CAP


def test_keyed_integrity_epoch40(roster_from_binary: dict):
    """Epoch 40 accepted matches restored attestation."""
    epochs = _epoch_map(roster_from_binary)
    assert int(epochs[40]["accepted"]) == EPOCH_40_ACCEPTED


def test_replay_detection_epoch10(roster_from_binary: dict):
    """Epoch 10 rejects replayed credentials."""
    epochs = _epoch_map(roster_from_binary)
    assert int(epochs[10]["accepted"]) == EPOCH_10_ACCEPTED


def test_replay_detection_epoch20(roster_from_binary: dict):
    """Epoch 20 rejects replayed credentials."""
    epochs = _epoch_map(roster_from_binary)
    assert int(epochs[20]["accepted"]) == EPOCH_20_ACCEPTED


def test_replay_detection_epoch50(roster_from_binary: dict):
    """Epoch 50 rejects replayed credentials."""
    epochs = _epoch_map(roster_from_binary)
    assert int(epochs[50]["accepted"]) == EPOCH_50_ACCEPTED


def test_revocation_epoch20(roster_from_binary: dict):
    """Epoch 20 reflects ledger revocation."""
    epochs = _epoch_map(roster_from_binary)
    assert int(epochs[20]["accepted"]) == EPOCH_20_ACCEPTED


def test_hold_semantics_epoch30(roster_from_binary: dict):
    """Epoch 30 publishes with held co-presence (exact restored accepted)."""
    epochs = _epoch_map(roster_from_binary)
    assert EPOCH_THIRTY in epochs
    assert epochs[EPOCH_THIRTY]["profile"] == PROFILE_A
    assert int(epochs[EPOCH_THIRTY]["accepted"]) == EPOCH_30_ACCEPTED


def test_copresence_backends(roster_from_binary: dict):
    """Matrix lanes active; off-matrix inactive; deep path not surface-inflated."""
    statuses = _status_map(roster_from_binary)
    assert statuses.get("mqtt") == STATUS_ACTIVE
    assert statuses.get("lora") == STATUS_ACTIVE
    assert statuses.get("uart") == STATUS_ACTIVE
    assert statuses.get("canbus") == STATUS_INACTIVE
    assert statuses.get("zigbee") == STATUS_INACTIVE
    epochs = _epoch_map(roster_from_binary)
    surface = json.loads(SURFACE.read_text(encoding="utf-8"))
    surface_epochs = {int(e["id"]): e for e in surface["epochs"]}
    assert int(epochs[10]["accepted"]) < int(surface_epochs[10]["accepted"])
    assert int(epochs[20]["accepted"]) < int(surface_epochs[20]["accepted"])


def test_all_epochs_present(roster_from_binary: dict):
    """All five fleet epochs publish with correct profiles."""
    epochs = _epoch_map(roster_from_binary)
    assert set(epochs.keys()) == PUBLISHED_EPOCHS
    assert epochs[10]["profile"] == PROFILE_A
    assert epochs[20]["profile"] == PROFILE_A
    assert epochs[30]["profile"] == PROFILE_A
    assert epochs[40]["profile"] == PROFILE_B
    assert epochs[50]["profile"] == PROFILE_B


def test_revoked_lane_omits_epoch(roster_from_binary: dict):
    """Epoch with a required lane only-revoked must not publish."""
    epochs = _epoch_map(roster_from_binary)
    assert EPOCH_TWENTY_FIVE not in epochs
    assert set(epochs.keys()) == PUBLISHED_EPOCHS


def test_hold_keeps_epoch_with_reduced_accepted(roster_from_binary: dict):
    """Suspended co-presence keeps the epoch; accepted is only non-held trust."""
    epochs = _epoch_map(roster_from_binary)
    assert EPOCH_THIRTY in epochs
    assert epochs[EPOCH_THIRTY]["profile"] == PROFILE_A
    assert int(epochs[EPOCH_THIRTY]["accepted"]) == EPOCH_30_ACCEPTED
    assert int(epochs[EPOCH_THIRTY]["accepted"]) < BAND_CAP


def test_output_differs_from_surface(roster_from_binary: dict):
    """Deep attestation must disagree with the surface fixture on every shared epoch."""
    surface = json.loads(SURFACE.read_text(encoding="utf-8"))
    assert roster_from_binary != surface
    surface_epochs = {int(e["id"]): e for e in surface["epochs"]}
    roster_epochs = _epoch_map(roster_from_binary)
    for eid in sorted(PUBLISHED_EPOCHS):
        assert eid in roster_epochs
        assert int(roster_epochs[eid]["accepted"]) < int(surface_epochs[eid]["accepted"])


def test_output_matches_rebuilt(roster_from_binary: dict):
    """On-disk agent output must match rebuilt trusteval."""
    assert OUTPUT.is_file(), f"missing {OUTPUT}"
    on_disk = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert on_disk == roster_from_binary
    epochs = _epoch_map(on_disk)
    assert int(epochs[10]["accepted"]) == EPOCH_10_ACCEPTED


def test_attestation_stable_across_runs(roster_from_binary: dict):
    """Second attest run must match the first and stay below surface tallies."""
    second = _rebuild_and_attest(Path("/tmp") / "ceremony-ledger-second.json")
    assert second == roster_from_binary
    epochs = _epoch_map(second)
    assert int(epochs[EPOCH_TEN]["accepted"]) < SURFACE_EPOCH_10
    assert EPOCH_THIRTY in epochs


def test_output_differs_from_jarcheck(roster_from_binary: dict):
    """Agent output must differ from jarcheck and beat surface inflation."""
    surface_poke = json.loads(SURFACE.read_text(encoding="utf-8"))
    assert roster_from_binary != surface_poke
    assert OUTPUT.is_file()
    on_disk = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert on_disk == roster_from_binary
    assert on_disk != surface_poke
    assert Path("/app/bin").joinpath("jarcheck").is_file()
    epochs = _epoch_map(on_disk)
    poke_epochs = {int(e["id"]): e for e in surface_poke["epochs"]}
    assert int(epochs[10]["accepted"]) < int(poke_epochs[10]["accepted"])


def test_dynamic_frame_injection():
    """Inject a valid frame and verify the evaluator incorporates it."""
    seg_path = SEGMENTS / "seg_99.bin"
    assert DYNAMIC_FRAME.is_file(), "dynamic test frame fixture missing"
    shutil.copy(DYNAMIC_FRAME, seg_path)
    try:
        roster = _rebuild_and_attest(DYNAMIC_OUT)
        epochs = _epoch_map(roster)
        assert int(epochs[10]["accepted"]) == EPOCH_10_ACCEPTED + 1, (
            f"Expected {EPOCH_10_ACCEPTED + 1} after injection, got {epochs[10]['accepted']}"
        )
    finally:
        seg_path.unlink(missing_ok=True)


def test_dynamic_injected_frame_rejected():
    """Inject a forged frame and verify it is rejected."""
    seg_path = SEGMENTS / "seg_98.bin"
    assert DYNAMIC_INJECTED.is_file(), "dynamic injected frame fixture missing"
    shutil.copy(DYNAMIC_INJECTED, seg_path)
    try:
        roster = _rebuild_and_attest(DYNAMIC_OUT)
        epochs = _epoch_map(roster)
        assert int(epochs[40]["accepted"]) == EPOCH_40_ACCEPTED, (
            f"Expected {EPOCH_40_ACCEPTED} (injected rejected), got {epochs[40]['accepted']}"
        )
    finally:
        seg_path.unlink(missing_ok=True)


def test_dynamic_legacy_binding_rejected():
    """Payload-only legacy signatures must not raise accepted tallies."""
    seg_path = SEGMENTS / "seg_97.bin"
    assert DYNAMIC_LEGACY.is_file(), "dynamic legacy frame fixture missing"
    shutil.copy(DYNAMIC_LEGACY, seg_path)
    try:
        roster = _rebuild_and_attest(DYNAMIC_OUT)
        epochs = _epoch_map(roster)
        assert int(epochs[40]["accepted"]) == EPOCH_40_ACCEPTED
    finally:
        seg_path.unlink(missing_ok=True)


def test_watermark_boundary_included(roster_from_binary: dict):
    """On-watermark credential at epoch 10 contributes to accepted."""
    epochs = _epoch_map(roster_from_binary)
    assert int(epochs[EPOCH_TEN]["accepted"]) == EPOCH_10_ACCEPTED


def test_integrity_count_exact(
    roster_from_binary: dict, quarantine_from_binary: dict
):
    """Agent quarantine integrity set matches rebuilt trusteval."""
    _ = roster_from_binary
    agent = _load_quarantine(QUARANTINE)
    assert _reason_keys(agent, REASON_INTEGRITY) == _reason_keys(
        quarantine_from_binary, REASON_INTEGRITY
    )


def test_quarantine_structure(
    roster_from_binary: dict, quarantine_from_binary: dict
):
    """Quarantine shape and reason vocabulary match rebuilt trusteval."""
    _ = roster_from_binary
    assert QUARANTINE.is_file(), f"missing {QUARANTINE}"
    agent = _load_quarantine(QUARANTINE)
    assert len(agent["rejected"]) == len(quarantine_from_binary["rejected"])
    reasons = {e["reason"] for e in agent["rejected"]}
    assert REASON_INTEGRITY in reasons
    assert REASON_REPLAY in reasons
    assert REASON_REVOKED in reasons
    for entry in agent["rejected"]:
        assert KEY_EPOCH in entry
        assert KEY_LANE in entry
        assert KEY_TS in entry
        assert entry["reason"] in QUARANTINE_REASONS


def test_quarantine_integrity_failures(
    roster_from_binary: dict, quarantine_from_binary: dict
):
    """integrity_failure rows match the rebuilt oracle set."""
    _ = roster_from_binary
    agent = _load_quarantine(QUARANTINE)
    assert _reason_keys(agent, REASON_INTEGRITY) == _reason_keys(
        quarantine_from_binary, REASON_INTEGRITY
    )
    assert len(_reason_keys(agent, REASON_INTEGRITY)) >= 1


def test_quarantine_replay_entries(
    roster_from_binary: dict, quarantine_from_binary: dict
):
    """replay rows match the rebuilt oracle set."""
    _ = roster_from_binary
    agent = _load_quarantine(QUARANTINE)
    assert _reason_keys(agent, REASON_REPLAY) == _reason_keys(
        quarantine_from_binary, REASON_REPLAY
    )
    assert len(_reason_keys(agent, REASON_REPLAY)) >= 1


def test_quarantine_revoked_entries(
    roster_from_binary: dict, quarantine_from_binary: dict
):
    """revoked rows match the rebuilt oracle set."""
    _ = roster_from_binary
    agent = _load_quarantine(QUARANTINE)
    assert _reason_keys(agent, REASON_REVOKED) == _reason_keys(
        quarantine_from_binary, REASON_REVOKED
    )
    assert len(_reason_keys(agent, REASON_REVOKED)) >= 1


def test_quarantine_matches_rebuilt(
    roster_from_binary: dict, quarantine_from_binary: dict
):
    """On-disk quarantine equals rebuilt trusteval quarantine."""
    _ = roster_from_binary
    agent = _load_quarantine(QUARANTINE)
    assert agent == quarantine_from_binary


def test_fixtures_untouched():
    """Seed and surface fixtures remain as shipped."""
    data = json.loads(SEED.read_text(encoding="utf-8"))
    assert data.get("seed") == SEED_NAME
    assert data.get("preserve") is True
    surface = json.loads(SURFACE.read_text(encoding="utf-8"))
    assert surface.get("version") == SCHEMA_VERSION
    assert int(surface["epochs"][0]["accepted"]) == SURFACE_EPOCH_10
    audit = (FIXTURES / "pre_incident_audit.log").read_text(encoding="utf-8")
    assert SAMPLE_A in audit
    assert SAMPLE_B in audit
    assert SAMPLE_C in audit
    assert len(re.findall(r"seed_hex=[0-9a-f]{8}", audit)) >= 3
    assert len(re.findall(r"sk_hex=[0-9a-f]{64}", audit)) >= 3
    assert len(re.findall(r"pubkey_hex=[0-9a-f]{64}", audit)) >= 3
    assert len(re.findall(r"sig_hex=[0-9a-f]{128}", audit)) >= 3
    assert len(re.findall(r"message_hex=[0-9a-f]+", audit)) >= 3
    assert "key_dom_hex=" in audit
    assert "domain_ascii=WAUV" in audit

"""Storm budget verifier — expectations derived from public overlay/ledger contracts.

Distinct n3_v1 storm-budget grid contract fingerprint for collapse hygiene.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
REPORT = Path("/app/output/storm_trace.json")
AUDIT = Path("/app/output/replay_audit.json")
UNIT_SG = ENV / "pack/w8/sg.slice"
UNIT_SD = ENV / "pack/w8/sd.slice"
INC_SG = ENV / "pack/incidents/sg.inc"
INC_SD = ENV / "pack/incidents/sd.inc"
STAGING = ENV / "pack/seed/.anchor_staging"
LEDGER = ENV / "pack/ledger/waves.ndjson"
POLICY_DIR = ENV / "pack/policy"
INTER = ENV / "pack/inter_m5.json"
BUNDLES = ("wave_alpha", "wave_beta", "wave_gamma", "wave_delta")
PROFILE_FILES = {
    "wave_alpha": "prf_w1.json",
    "wave_beta": "prf_w2.json",
    "wave_gamma": "prf_w3.json",
    "wave_delta": "prf_w4.json",
}
STAGING_ANCHOR_DISTINCT = b"HOTSTG01"
DIGEST_HEX_LEN = 64
_PROBE_STATE: dict[str, str | None] = {"bin": None}


def _burst_require(condition: bool, message: str = "") -> None:
    if not condition:
        raise AssertionError(message)


def compile_workspace() -> None:
    proc = subprocess.run(
        ["bash", "/app/environment/scripts/build_all.sh"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"build failed:\n{proc.stderr}")


def _ensure_probe_built() -> str:
    probe_bin = "/app/environment/.libprobe"
    cached = _PROBE_STATE["bin"]
    if cached is not None:
        return cached
    env = {
        **os.environ,
        "PATH": "/usr/local/go/bin:" + os.environ.get("PATH", ""),
        "GOWORK": "off",
        "GOCACHE": "/tmp/tb-gocache",
    }
    build = subprocess.run(
        ["go", "build", "-a", "-o", probe_bin, "."],
        cwd=str(Path("/tests") / "lib_probe"),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if build.returncode != 0:
        raise AssertionError(
            "library probe build failed:\n"
            f"stdout:\n{build.stdout}\nstderr:\n{build.stderr}"
        )
    _PROBE_STATE["bin"] = probe_bin
    return probe_bin


def run_library_probe(check: str | None = None) -> str:
    """Compile and run direct package probes under k4/graph, m2/limit, p8/g9, ld, pol."""
    probe_bin = _ensure_probe_built()
    env = {
        **os.environ,
        "PATH": "/usr/local/go/bin:" + os.environ.get("PATH", ""),
        "GOWORK": "off",
        "GOCACHE": "/tmp/tb-gocache",
    }
    if check is None:
        proc = subprocess.run(
            [probe_bin],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    else:
        proc = subprocess.run(
            [probe_bin, check],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    if proc.returncode != 0:
        raise AssertionError(
            "library probe failed:\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc.stdout.strip()


def invoke_driver(*, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if REPORT.exists():
        REPORT.unlink()
    if AUDIT.exists():
        AUDIT.unlink()
    proc = subprocess.run(
        [
            "/app/environment/bin/wave_sched",
            "--grid-full",
            "--out",
            str(REPORT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if expect_ok and proc.returncode != 0:
        raise AssertionError(f"driver failed:\n{proc.stderr}")
    return proc


def load_report() -> dict:
    if not REPORT.is_file():
        raise AssertionError("graded report missing after driver run")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    if payload.get("format") != "n3_v1":
        raise AssertionError("unexpected report format tag")
    return payload


def load_audit() -> dict:
    if not AUDIT.is_file():
        raise AssertionError("replay_audit missing after driver run")
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def bundle_row(payload: dict, name: str) -> dict:
    for entry in payload["grid"]:
        if entry["family"] == name:
            return entry
    raise KeyError(name)


def blob_fingerprint(path: Path) -> str:
    proc = subprocess.run(
        ["sha256sum", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.split()[0]


def ledger_tip_gen() -> int:
    """Public tip rule from policy_overlay.md / field_layout.md."""
    tip = -1
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("tomb"):
            continue
        tip = max(tip, int(rec["gen"]))
    return max(tip, 0)


def load_overlay_for_tip(tip: int) -> tuple[dict, str]:
    """Public pick rule: ov_g{N}.json for tip N."""
    path = POLICY_DIR / f"ov_g{tip}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    rel = f"pack/policy/ov_g{tip}.json"
    return doc, rel


def read_anchor_bytes(policy_gen: int) -> bytes:
    cp = ENV / "pack/checkpoints" / f"stg_g{policy_gen}.bin"
    if cp.is_file():
        data = cp.read_bytes()
        if len(data) >= 8:
            return data[:8]
    if STAGING.is_file():
        data = STAGING.read_bytes()
        if len(data) >= 8:
            return data[:8]
    return b"N3ANCHOR"


def parse_cell(cell: bytes, *, permute: bool, swap_masks: bool) -> list[dict]:
    if len(cell) < 6 or cell[:4] != b"CELL":
        raise ValueError("bad cell")
    count = cell[5]
    arms: list[dict] = []
    off = 6
    for _ in range(count):
        arm_id = cell[off]
        kind = cell[off + 1]
        mask = struct.unpack_from("<H", cell, off + 2)[0]
        shadow = cell[off + 4]
        seq = cell[off + 5]
        arms.append(
            {
                "id": arm_id,
                "kind": kind,
                "mask": mask,
                "shadow": shadow,
                "seq": seq,
            }
        )
        off += 6
    if permute and len(arms) >= 3:
        arms[1], arms[2] = arms[2], arms[1]
    if swap_masks and len(arms) >= 3:
        arms[1]["mask"], arms[2]["mask"] = arms[2]["mask"], arms[1]["mask"]
    return arms


def parse_wave(wave: bytes) -> list[int]:
    if len(wave) < 6 or wave[:4] != b"WAVE":
        raise ValueError("bad wave")
    count = struct.unpack_from("<H", wave, 4)[0]
    return list(wave[6 : 6 + count])


def weave_reference(arms: list[dict], radius: int) -> list[int]:
    order = sorted(arms, key=lambda a: a["seq"])
    suppressed: set[int] = set()
    for arm in order:
        if arm["kind"] != 2:
            continue
        if arm["shadow"] == 0:
            continue
        link = arm["shadow"]
        for other in arms:
            if other["kind"] != 1:
                continue
            if (other["mask"] & arm["mask"]) == 0:
                continue
            if abs(other["id"] - link) >= radius:
                suppressed.add(other["id"])
    active: list[int] = []
    for arm in order:
        if arm["kind"] == 1 and arm["id"] not in suppressed:
            active.append(arm["id"])
    return active


def tally_reference(active: list[dict], events: list[int]) -> list[tuple[int, int]]:
    scored: list[tuple[int, int]] = []
    for arm in active:
        hits = 0
        for field in events:
            if field & arm["mask"]:
                hits += 1
        scored.append((arm["id"], hits))
    return scored


def seek_reference(
    scored: list[tuple[int, int]], budget: int, anchor: bytes
) -> tuple[list[int], bytes]:
    decorated = []
    for arm_id, score in scored:
        tie = anchor[arm_id % 8]
        decorated.append((arm_id, score, tie))
    decorated.sort(key=lambda row: (-row[1], -row[2], row[0]))
    take = min(budget, len(decorated))
    lane_order = [row[0] for row in decorated[:take]]
    return lane_order, anchor[:8]


def canonical_digest(
    cell: bytes,
    wave: bytes,
    masks: dict[int, int],
    lane_order: list[int],
    anchor: bytes,
) -> str:
    hasher = hashlib.sha256()
    hasher.update(cell)
    hasher.update(wave)
    for slot in lane_order:
        mask = masks.get(slot, 0)
        hasher.update(struct.pack("<H", mask))
        hasher.update(struct.pack("<B", slot))
    hasher.update(anchor[:8])
    return hasher.hexdigest()


def profile_doc(family: str) -> dict:
    return json.loads(
        (ENV / "profiles" / PROFILE_FILES[family]).read_text(encoding="utf-8")
    )


def reference_family_row(family: str) -> dict:
    tip = ledger_tip_gen()
    overlay, overlay_rel = load_overlay_for_tip(tip)
    radius = int(overlay["shadow_radius"])
    policy_gen = int(overlay["gen"])
    profile = profile_doc(family)
    cell = (ENV / "pack/w8" / f"{profile['unit_slice']}.slice").read_bytes()
    wave = (ENV / "pack/incidents" / f"{profile['incident_wave']}.inc").read_bytes()
    arms = parse_cell(
        cell,
        permute=profile.get("permute", False),
        swap_masks=profile.get("swap_masks", False),
    )
    events = parse_wave(wave)
    active_ids = weave_reference(arms, radius)
    active_arms = [a for a in arms if a["id"] in active_ids]
    scored = tally_reference(active_arms, events)
    anchor = read_anchor_bytes(policy_gen)
    lane_order, anchor_out = seek_reference(scored, profile["budget"], anchor)
    mask_map = {a["id"]: a["mask"] for a in active_arms}
    span_band = sum(score for _, score in scored)
    digest = canonical_digest(cell, wave, mask_map, lane_order, anchor_out)
    return {
        "family": family,
        "lane_order": lane_order,
        "span_band": span_band,
        "span_digest": digest,
        "cold_digest": digest,
        "hot_digest": digest,
        "band_limit": profile["band_limit"],
        "tip_gen": tip,
        "policy_gen": policy_gen,
        "policy_id": overlay["policy_id"],
        "policy_path": overlay_rel,
        "ledger_fingerprint": hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
    }


@pytest.fixture(scope="session", autouse=True)
def _storm_grid_ready() -> None:
    if not ENV.is_dir():
        raise AssertionError("environment root missing")
    compile_workspace()


@pytest.fixture(scope="session")
def _libprobe_ready() -> None:
    _ensure_probe_built()


def test_burst_probe_overlap_suppression(_libprobe_ready: None) -> None:
    """Overlap suppression must drop linked include arms before lane assembly."""
    run_library_probe("q7")
    run_library_probe("q8")
    run_library_probe("q9")
    run_library_probe("q16")


def test_burst_probe_family_hit_epochs(_libprobe_ready: None) -> None:
    """Family burst tallies must isolate, keep hit epochs aligned, and refresh on byte changes."""
    run_library_probe("q10")
    run_library_probe("q12")
    run_library_probe("q11")
    run_library_probe("q15")
    run_library_probe("q18")


def test_burst_probe_staged_tie_bytes(_libprobe_ready: None) -> None:
    """Equal scores must rank with descending staged-anchor bytes then ascending arm id."""
    run_library_probe("q13")
    run_library_probe("q14")


def test_ledger_overlay_coupling_probe(_libprobe_ready: None) -> None:
    """Ledger tip must ignore tombstones and select the matching overlay generation."""
    run_library_probe("q17")


def test_wave_gamma_tally_not_inherited() -> None:
    """Held wave_gamma must not inherit hit vectors from an earlier sg bundle in the same grid run."""
    invoke_driver()
    live = bundle_row(load_report(), "wave_gamma")
    ref = reference_family_row("wave_gamma")
    _burst_require(live["span_band"] == ref["span_band"])
    _burst_require(live["lane_order"] == ref["lane_order"])
    _burst_require(live["span_digest"] == ref["span_digest"])


def test_cold_hot_digest_triplet_agreement() -> None:
    """Cold vs hot paths agree on graded digests with valid triplet alignment per bundle."""
    invoke_driver()
    doc = load_report()
    for family in BUNDLES:
        live = bundle_row(doc, family)
        ref = reference_family_row(family)
        _burst_require(len(live["span_digest"]) == DIGEST_HEX_LEN)
        _burst_require(live["span_digest"] == live["cold_digest"] == live["hot_digest"])
        _burst_require(live["span_digest"] == ref["span_digest"])


def test_replay_audit_matches_ledger_overlay() -> None:
    """replay_audit tip_gen and overlay fields must match public ledger and overlay rules."""
    invoke_driver()
    audit = load_audit()
    ref = reference_family_row("wave_alpha")
    _burst_require(audit["tip_gen"] == ref["tip_gen"])
    _burst_require(audit["policy_gen"] == ref["policy_gen"])
    _burst_require(audit["policy_id"] == ref["policy_id"])
    _burst_require(audit["policy_path"] == ref["policy_path"])
    _burst_require(audit["ledger_fingerprint"] == ref["ledger_fingerprint"])


def test_preserve_anchor_replay_digest_stability() -> None:
    """Preserve-anchor recovery followed by two grid replays must keep span_digest stable."""
    before = {
        family: reference_family_row(family)["span_digest"] for family in BUNDLES
    }
    subprocess.run(
        ["bash", "/app/environment/phase/rld_x2.sh", "--preserve-anchor"],
        check=True,
    )
    invoke_driver()
    first = {
        family: bundle_row(load_report(), family)["span_digest"] for family in BUNDLES
    }
    invoke_driver()
    second = {
        family: bundle_row(load_report(), family)["span_digest"] for family in BUNDLES
    }
    _burst_require(first == second)
    _burst_require(first == before)
    audit = load_audit()
    _burst_require(audit["tip_gen"] == 0)
    _burst_require(audit["policy_gen"] == 0)


def test_budget_lane_order_matches_scoring_rule() -> None:
    """lane_order must follow score, staged anchor tie-break, then ascending arm id ordering."""
    invoke_driver()
    doc = load_report()
    for family in BUNDLES:
        live = bundle_row(doc, family)
        ref = reference_family_row(family)
        _burst_require(live["lane_order"] == ref["lane_order"])


def test_interim_smoke_digests_are_not_graded() -> None:
    """Interim decoy rows alone do not satisfy terminal report grading."""
    inter = json.loads(INTER.read_text(encoding="utf-8"))
    invoke_driver()
    doc = load_report()
    for row in inter["rows"]:
        family = row["family"]
        live = bundle_row(doc, family)
        _burst_require(live["span_digest"] != row["span_digest"])


def test_storm_gen_poison_blocks_n3_emit() -> None:
    """Bare resets poison generation ledger and block n3_v1 until preserve-anchor."""
    storm_gen = ENV / "pack/seed/.storm_gen"
    try:
        invoke_driver()
        subprocess.run(["bash", "/app/environment/phase/rld_x2.sh"], check=True)
        gen_raw = storm_gen.read_text(encoding="utf-8").strip()
        _burst_require(gen_raw != "0")
        proc_mid = invoke_driver(expect_ok=False)
        assert proc_mid.returncode != 0
        if REPORT.exists():
            assert json.loads(REPORT.read_text(encoding="utf-8")).get("format") != "n3_v1"
        subprocess.run(["bash", "/app/environment/phase/rld_x2.sh"], check=True)
        proc = invoke_driver(expect_ok=False)
        assert proc.returncode != 0
        if REPORT.exists():
            assert json.loads(REPORT.read_text(encoding="utf-8")).get("format") != "n3_v1"
        _burst_require(storm_gen.read_text(encoding="utf-8").strip() != "0")
    finally:
        subprocess.run(
            ["bash", "/app/environment/phase/rld_x2.sh", "--preserve-anchor"],
            check=True,
        )
        _burst_require(storm_gen.read_text(encoding="utf-8").strip() == "0")
        _burst_require(ledger_tip_gen() == 0)


def test_hotstg_prefix_blocks_n3_emit() -> None:
    """Non-default .anchor_staging bytes must drive hot-path when no matching checkpoint binds tip."""
    _burst_require(STAGING_ANCHOR_DISTINCT != b"N3ANCHOR")
    original = STAGING.read_bytes() if os.path.isfile(str(STAGING)) else None
    tip = ledger_tip_gen()
    cp = ENV / "pack/checkpoints" / f"stg_g{tip}.bin"
    cp_orig = cp.read_bytes() if cp.exists() else None
    try:
        if cp.exists():
            cp.unlink()
        STAGING.write_bytes(STAGING_ANCHOR_DISTINCT)
        proc = invoke_driver(expect_ok=False)
        _burst_require(proc.returncode != 0)
        if REPORT.exists():
            payload = json.loads(REPORT.read_text(encoding="utf-8"))
            _burst_require(payload.get("format") != "n3_v1")
    finally:
        if cp_orig is not None:
            cp.write_bytes(cp_orig)
        if original is not None:
            STAGING.write_bytes(original)
        elif os.path.isfile(str(STAGING)):
            STAGING.unlink()


def test_preserve_keeps_pack_slice_fingerprints() -> None:
    """Documented recovery after ops reset preserves fragment/incident slice integrity."""
    before = {
        "sg_unit": blob_fingerprint(UNIT_SG),
        "sd_unit": blob_fingerprint(UNIT_SD),
        "sg_incident": blob_fingerprint(INC_SG),
        "sd_incident": blob_fingerprint(INC_SD),
    }
    subprocess.run(
        ["bash", "/app/environment/phase/rld_x2.sh", "--preserve-anchor"],
        check=True,
    )
    after = {
        "sg_unit": blob_fingerprint(UNIT_SG),
        "sd_unit": blob_fingerprint(UNIT_SD),
        "sg_incident": blob_fingerprint(INC_SG),
        "sd_incident": blob_fingerprint(INC_SD),
    }
    _burst_require(before == after)
    invoke_driver(expect_ok=True)
    live = bundle_row(load_report(), "wave_alpha")
    ref = reference_family_row("wave_alpha")
    _burst_require(live["span_digest"] == ref["span_digest"])


def test_span_band_equals_active_include_hits() -> None:
    """span_band sums every active include arm after suppression, not only lane_order members."""
    invoke_driver()
    doc = load_report()
    for family in BUNDLES:
        live = bundle_row(doc, family)
        ref = reference_family_row(family)
        _burst_require(live["span_band"] == ref["span_band"])
        if family == "wave_delta":
            _burst_require(live["span_band"] <= ref["band_limit"])


def test_swap_masks_uses_decoded_masks_for_hits() -> None:
    """swap_masks profiles must tally with decoded masks while digest prefixes hash raw slice bytes."""
    invoke_driver()
    live = bundle_row(load_report(), "wave_delta")
    ref = reference_family_row("wave_delta")
    tip = ledger_tip_gen()
    overlay, _overlay_rel = load_overlay_for_tip(tip)
    radius = int(overlay["shadow_radius"])
    policy_gen = int(overlay["gen"])
    profile = profile_doc("wave_delta")
    cell = (ENV / "pack/w8" / f"{profile['unit_slice']}.slice").read_bytes()
    wave = (ENV / "pack/incidents" / f"{profile['incident_wave']}.inc").read_bytes()
    arms_decoded = parse_cell(cell, permute=False, swap_masks=True)
    arms_raw = parse_cell(cell, permute=False, swap_masks=False)
    events = parse_wave(wave)
    active_ids = weave_reference(arms_decoded, radius)
    active_decoded = [a for a in arms_decoded if a["id"] in active_ids]
    active_raw = [a for a in arms_raw if a["id"] in active_ids]
    band_decoded = sum(score for _, score in tally_reference(active_decoded, events))
    band_raw = sum(score for _, score in tally_reference(active_raw, events))
    _burst_require(live["span_band"] == ref["span_band"])
    _burst_require(live["span_band"] == band_decoded)
    if band_decoded != band_raw:
        _burst_require(live["span_band"] != band_raw)
    anchor = read_anchor_bytes(policy_gen)
    lane_order, anchor_out = seek_reference(
        tally_reference(active_decoded, events),
        profile["budget"],
        anchor,
    )
    mask_map_decoded = {a["id"]: a["mask"] for a in active_decoded}
    mask_map_raw = {a["id"]: a["mask"] for a in active_raw}
    digest_decoded = canonical_digest(cell, wave, mask_map_decoded, lane_order, anchor_out)
    digest_raw_masks = canonical_digest(cell, wave, mask_map_raw, lane_order, anchor_out)
    _burst_require(live["span_digest"] == digest_decoded)
    if mask_map_decoded != mask_map_raw:
        _burst_require(digest_decoded != digest_raw_masks)


def test_one_byte_staging_flip_blocks_n3() -> None:
    """When only one staging byte differs from token_seed and checkpoint is unbound, n3_v1 must not emit."""
    seed_path = ENV / "pack/seed/token_seed.bin"
    seed_bytes = seed_path.read_bytes()
    _burst_require(len(seed_bytes) >= 8)
    mismatched = bytearray(seed_bytes[:8])
    mismatched[7] ^= 0x01
    original = STAGING.read_bytes() if STAGING.exists() else None
    tip = ledger_tip_gen()
    cp = ENV / "pack/checkpoints" / f"stg_g{tip}.bin"
    cp_orig = cp.read_bytes() if cp.exists() else None
    try:
        if cp.exists():
            cp.unlink()
        STAGING.write_bytes(bytes(mismatched))
        proc = invoke_driver(expect_ok=False)
        _burst_require(proc.returncode != 0)
        if REPORT.exists():
            payload = json.loads(REPORT.read_text(encoding="utf-8"))
            _burst_require(payload.get("format") != "n3_v1")
    finally:
        if cp_orig is not None:
            cp.write_bytes(cp_orig)
        if original is not None:
            STAGING.write_bytes(original)
        elif STAGING.exists():
            STAGING.unlink()


def test_permute_digest_hashes_raw_slice_bytes() -> None:
    """Digest prefix must hash on-disk slice and wave bytes even when permute reshapes scoring."""
    invoke_driver()
    live = bundle_row(load_report(), "wave_gamma")
    ref = reference_family_row("wave_gamma")
    _burst_require(live["span_digest"] == ref["span_digest"])
    tip = ledger_tip_gen()
    overlay, _overlay_rel = load_overlay_for_tip(tip)
    radius = int(overlay["shadow_radius"])
    policy_gen = int(overlay["gen"])
    profile = profile_doc("wave_gamma")
    cell = (ENV / "pack/w8" / f"{profile['unit_slice']}.slice").read_bytes()
    wave = (ENV / "pack/incidents" / f"{profile['incident_wave']}.inc").read_bytes()
    arms_scored = parse_cell(cell, permute=True, swap_masks=False)
    arms_raw = parse_cell(cell, permute=False, swap_masks=False)
    events = parse_wave(wave)
    active_ids = weave_reference(arms_scored, radius)
    active_arms = [a for a in arms_scored if a["id"] in active_ids]
    scored = tally_reference(active_arms, events)
    anchor = read_anchor_bytes(policy_gen)
    lane_order, anchor_out = seek_reference(scored, profile["budget"], anchor)
    mask_map_scored = {a["id"]: a["mask"] for a in active_arms}
    mask_map_raw = {a["id"]: a["mask"] for a in arms_raw if a["id"] in active_ids}
    digest_raw = canonical_digest(cell, wave, mask_map_raw, lane_order, anchor_out)
    digest_scored = canonical_digest(cell, wave, mask_map_scored, lane_order, anchor_out)
    _burst_require(live["span_digest"] == digest_raw)
    if mask_map_raw != mask_map_scored:
        _burst_require(digest_raw != digest_scored)


def test_seed_matched_staging_recovers_convergence() -> None:
    """When .anchor_staging matches the cold seed prefix under tip-coherent checkpoints, digests converge."""
    seed_path = ENV / "pack/seed/token_seed.bin"
    seed_prefix = seed_path.read_bytes()[:8]
    original = STAGING.read_bytes() if STAGING.exists() else None
    tip = ledger_tip_gen()
    cp = ENV / "pack/checkpoints" / f"stg_g{tip}.bin"
    cp_orig = cp.read_bytes() if cp.exists() else None
    try:
        STAGING.write_bytes(seed_prefix)
        if cp.exists():
            cp.write_bytes(seed_prefix)
        invoke_driver(expect_ok=True)
        doc = load_report()
        for family in BUNDLES:
            live = bundle_row(doc, family)
            ref = reference_family_row(family)
            _burst_require(live["span_digest"] == live["cold_digest"] == live["hot_digest"])
            _burst_require(live["span_digest"] == ref["span_digest"])
    finally:
        if cp_orig is not None:
            cp.write_bytes(cp_orig)
        if original is not None:
            STAGING.write_bytes(original)
        elif STAGING.exists():
            STAGING.unlink()

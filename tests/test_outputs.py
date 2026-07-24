"""Scientific-computing verifier for GF(256) Model 2 channel-coding numerics.

Every expected value is recomputed at test time by the independent
qr_reference algebraic model or by an external conforming Model 2 decode of
the published module matrices. Nothing is compared against stored outputs, so
hardcoded artifacts cannot satisfy this suite.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest
from qr_reference import (
    ECC_BLOCKS,
    GF_EXP,
    encode_symbol,
    gf_mul,
    reference_payloads,
    rs_syndromes,
    sha256_hex,
    symbol_size,
)

BIN = "/app/bin/qr-composer"
STATE = Path("/app/state")
OUTPUT = Path("/app/output/labels")
PUBLIC_INBOX = Path("/app/fixtures/shipbatch-inbox")
MANIFEST = OUTPUT / "label-run-manifest.json"

PIPELINE = (
    "ingest-shipbatches",
    "plan-symbols",
    "assemble-codewords",
    "protect-blocks",
    "interleave-streams",
    "run-mask-tournament",
    "emit-labels",
)

MODE_NAMES = ("numeric", "alphanumeric", "byte")

# ---------------------------------------------------------------------------
# Seeded hidden batch generation (derived at verify time, never shipped)
# ---------------------------------------------------------------------------

HIDDEN_SEED = 20260721
ALNUM_POOL = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
BYTE_POOL = "abcdefghijklmnopqrstuvwxyz{}~!@#_=;,?"


def seeded_hidden_payloads() -> list[dict]:
    rng = random.Random(HIDDEN_SEED)
    payloads = []
    pools = [
        "0123456789",
        ALNUM_POOL,
        BYTE_POOL,
        ALNUM_POOL + BYTE_POOL,
        "0123456789" + BYTE_POOL,
    ]
    idx = 0
    while len(payloads) < 10:
        n = rng.randint(6, 320)
        text = "".join(rng.choice(pools[idx % len(pools)]) for _ in range(n))
        level = "LMQH"[idx % 4]
        idx += 1
        try:
            encode_symbol(text, level)
        except ValueError:
            continue
        payloads.append(
            {"payload_id": f"h-{len(payloads):03d}", "ecc_level": level, "text": text}
        )
    # Crafted trap payloads. Trap conditions are asserted below, so a table
    # change cannot silently disarm them.
    payloads.append({"payload_id": "h-numtail", "ecc_level": "M", "text": "37788219004512"})
    payloads.append({"payload_id": "h-switch", "ecc_level": "L", "text": "cargo bay 9 lot 00042771 recheck 55"})
    payloads.append(
        {
            "payload_id": "h-class1",
            "ecc_level": "L",
            "text": ("relay pouch inventory " * 14).strip(),
        }
    )
    payloads.append(
        {
            "payload_id": "h-groups",
            "ecc_level": "Q",
            "text": "optics crate 4451 lane 02 seal unbroken net 88kg",
        }
    )
    return payloads


def assert_trap_conditions() -> None:
    by_id = {p["payload_id"]: p for p in seeded_hidden_payloads()}
    numtail = encode_symbol(by_id["h-numtail"]["text"], "M")
    assert any(
        seg["mode"] == "numeric" and seg["char_count"] % 3 == 2
        for seg in numtail["plan"]["segments"]
    )
    class1 = encode_symbol(by_id["h-class1"]["text"], "L")
    assert class1["version"] >= 10
    groups = encode_symbol(by_id["h-groups"]["text"], "Q")
    assert groups["block_structure"]["group2_blocks"] >= 1
    switch = encode_symbol(by_id["h-switch"]["text"], "L")
    assert switch["plan"]["segment_count"] >= 3


def write_hidden_inbox(tmp_path: Path) -> Path:
    inbox = tmp_path / "hidden-inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    payloads = seeded_hidden_payloads()
    batch = {"batch_id": "hx-901", "payloads": payloads}
    lines = ["{", f'  "batch_id": "{batch["batch_id"]}",', '  "payloads": [']
    for i, p in enumerate(payloads):
        comma = "," if i + 1 < len(payloads) else ""
        lines.append(
            f'    {{"payload_id": "{p["payload_id"]}", "ecc_level": "{p["ecc_level"]}", '
            f'"text": "{p["text"]}"}}{comma}'
        )
    lines.append("  ]")
    lines.append("}")
    (inbox / "hx-901.shipbatch.json").write_text("\n".join(lines) + "\n", encoding="ascii")
    return inbox


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_cli(*args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.pop("TB3_SHIPBATCH_INBOX", None)
    if env:
        merged.update(env)
    return subprocess.run([BIN, *args], capture_output=True, text=True, env=merged, check=False)


def rebuild_binary() -> None:
    proc = subprocess.run(["rebuild-qr-composer"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr


def reset_workspace() -> None:
    if STATE.exists():
        shutil.rmtree(STATE)
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    assert run_cli("init-store").returncode == 0


def run_pipeline(env: dict | None = None) -> None:
    reset_workspace()
    for step in PIPELINE:
        proc = run_cli(step, env=env)
        assert proc.returncode == 0, f"{step}: rc={proc.returncode} err={proc.stderr}"


def read_tsv(path: Path) -> list[list[str]]:
    rows = []
    for line in path.read_text(encoding="ascii").splitlines():
        if line:
            rows.append(line.split("\t"))
    return rows


def zbar_decode(pgm_path: str) -> str:
    proc = subprocess.run(
        ["zbarimg", "--quiet", "--raw", "-Sdisable", "-Sqrcode.enable", pgm_path],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"zbar failed on {pgm_path}: rc={proc.returncode} {proc.stderr}"
    return proc.stdout.rstrip("\n")


def manifest_symbols() -> dict[tuple[str, str], dict]:
    data = json.loads(MANIFEST.read_text(encoding="ascii"))
    assert data["schema"] == "label-run/1"
    return {(s["batch_id"], s["payload_id"]): s for s in data["symbols"]}


def public_refs() -> dict[tuple[str, str], dict]:
    return {
        (p["batch_id"], p["payload_id"]): encode_symbol(p["text"], p["ecc_level"])
        for p in reference_payloads(PUBLIC_INBOX)
    }


# ---------------------------------------------------------------------------
# Build and bootstrap
# ---------------------------------------------------------------------------


def test_rebuild_installs_binary() -> None:
    """The locked cmake rebuild path must reinstall /app/bin/qr-composer."""
    rebuild_binary()
    assert os.path.isfile(BIN)
    assert os.access(BIN, os.X_OK)


def test_init_store_creates_directories() -> None:
    """init-store must create /app/state and /app/output/labels per cli-surface.md."""
    reset_workspace()
    assert STATE.is_dir()
    assert OUTPUT.is_dir()


def test_status_lists_stage_artifacts() -> None:
    """status must report all eight stage artifacts present after a full run."""
    run_pipeline()
    proc = run_cli("status")
    assert proc.returncode == 0
    assert proc.stdout.count("present") == 8


# ---------------------------------------------------------------------------
# Ingest stage
# ---------------------------------------------------------------------------


def test_ingest_persists_sorted_payload_rows() -> None:
    """ingest-shipbatches must persist sorted payload rows per staging-schema.md."""
    reset_workspace()
    assert run_cli("ingest-shipbatches").returncode == 0
    rows = read_tsv(STATE / "payloads.tsv")
    expected = reference_payloads(PUBLIC_INBOX)
    assert len(rows) == len(expected) >= 12
    for row, ref in zip(rows, expected):
        assert row[0] == ref["batch_id"]
        assert row[1] == ref["payload_id"]
        assert row[2] == ref["ecc_level"]
        assert bytes.fromhex(row[3]).decode("ascii") == ref["text"]


def test_ingest_env_inbox_override(tmp_path: Path) -> None:
    """TB3_SHIPBATCH_INBOX absolute override must replace the configured inbox."""
    inbox = write_hidden_inbox(tmp_path)
    reset_workspace()
    proc = run_cli("ingest-shipbatches", env={"TB3_SHIPBATCH_INBOX": str(inbox)})
    assert proc.returncode == 0
    rows = read_tsv(STATE / "payloads.tsv")
    assert len(rows) == len(seeded_hidden_payloads())
    assert all(row[0] == "hx-901" for row in rows)


def test_ingest_rejects_relative_env_inbox() -> None:
    """Relative TB3_SHIPBATCH_INBOX values must be rejected with non-zero exit."""
    reset_workspace()
    proc = run_cli("ingest-shipbatches", env={"TB3_SHIPBATCH_INBOX": "relative/dir"})
    assert proc.returncode != 0


# ---------------------------------------------------------------------------
# Plan stage
# ---------------------------------------------------------------------------


def test_plan_versions_and_classes_match_reference() -> None:
    """plan-symbols must pick the minimal version fixpoint per segmentation-dp.md."""
    run_pipeline()
    refs = public_refs()
    rows = read_tsv(STATE / "plans.tsv")
    assert len(rows) == len(refs)
    for row in rows:
        ref = refs[(row[0], row[1])]
        assert int(row[3]) == ref["version"], f"{row[:2]} version"
        assert int(row[4]) == ref["plan"]["cci_class"], f"{row[:2]} cci_class"
        assert int(row[5]) == ref["plan"]["total_bits"], f"{row[:2]} total_bits"
        assert int(row[6]) == ref["plan"]["segment_count"], f"{row[:2]} segment_count"


def test_plan_segments_match_reference_dp() -> None:
    """segments.tsv must carry the optimal DP segmentation per segmentation-dp.md."""
    run_pipeline()
    refs = public_refs()
    seg_rows = read_tsv(STATE / "segments.tsv")
    grouped: dict[tuple[str, str], list[list[str]]] = {}
    for row in seg_rows:
        grouped.setdefault((row[0], row[1]), []).append(row)
    for key, ref in refs.items():
        rows = sorted(grouped[key], key=lambda r: int(r[2]))
        want = ref["plan"]["segments"]
        assert len(rows) == len(want), f"{key} segment rows"
        for row, seg in zip(rows, want):
            assert row[3] == seg["mode"], f"{key} seg mode"
            assert int(row[4]) == seg["char_count"], f"{key} seg chars"
            assert int(row[5]) == seg["bit_count"], f"{key} seg bits"


def test_plan_hidden_boundary_payloads(tmp_path: Path) -> None:
    """Version fixpoint must hold on verifier-generated boundary payloads."""
    assert_trap_conditions()
    inbox = write_hidden_inbox(tmp_path)
    run_pipeline(env={"TB3_SHIPBATCH_INBOX": str(inbox)})
    by_id = {p["payload_id"]: p for p in seeded_hidden_payloads()}
    rows = {row[1]: row for row in read_tsv(STATE / "plans.tsv")}
    for pid, payload in by_id.items():
        ref = encode_symbol(payload["text"], payload["ecc_level"])
        row = rows[pid]
        assert int(row[3]) == ref["version"], f"{pid} version"
        assert int(row[4]) == ref["plan"]["cci_class"], f"{pid} cci_class"
        assert int(row[5]) == ref["plan"]["total_bits"], f"{pid} total_bits"


# ---------------------------------------------------------------------------
# Assemble stage
# ---------------------------------------------------------------------------


def test_assemble_codewords_match_reference() -> None:
    """assemble-codewords must emit terminated padded codewords per codeword-assembly.md."""
    run_pipeline()
    refs = public_refs()
    for row in read_tsv(STATE / "codewords.tsv"):
        ref = refs[(row[0], row[1])]
        assert int(row[2]) == len(ref["data_codewords"]), f"{row[:2]} codeword count"
        assert row[3] == ref["data_codewords"].hex(), f"{row[:2]} data codewords"


def test_assemble_hidden_numeric_tail(tmp_path: Path) -> None:
    """Numeric tail groups and mode switches must assemble per codeword-assembly.md."""
    inbox = write_hidden_inbox(tmp_path)
    run_pipeline(env={"TB3_SHIPBATCH_INBOX": str(inbox)})
    by_id = {p["payload_id"]: p for p in seeded_hidden_payloads()}
    rows = {row[1]: row for row in read_tsv(STATE / "codewords.tsv")}
    for pid in ("h-numtail", "h-switch", "h-class1"):
        payload = by_id[pid]
        ref = encode_symbol(payload["text"], payload["ecc_level"])
        assert rows[pid][3] == ref["data_codewords"].hex(), f"{pid} data codewords"


# ---------------------------------------------------------------------------
# Protect stage
# ---------------------------------------------------------------------------


def test_protect_block_split_matches_reference() -> None:
    """protect-blocks must split groups and compute RS ECC per rs-protection.md."""
    run_pipeline()
    refs = public_refs()
    grouped: dict[tuple[str, str], list[list[str]]] = {}
    for row in read_tsv(STATE / "blocks.tsv"):
        grouped.setdefault((row[0], row[1]), []).append(row)
    for key, ref in refs.items():
        rows = sorted(grouped[key], key=lambda r: int(r[2]))
        assert len(rows) == len(ref["blocks"]), f"{key} block count"
        for row, blk in zip(rows, ref["blocks"]):
            assert int(row[3]) == blk["group"], f"{key} block group"
            assert row[5] == blk["data"].hex(), f"{key} block data"
            assert row[6] == blk["ecc"].hex(), f"{key} block ecc"


def test_rs_codewords_have_zero_syndromes() -> None:
    """Every block codeword must have all-zero syndromes at roots alpha^0..alpha^(d-1)."""
    run_pipeline()
    checked = 0
    for row in read_tsv(STATE / "blocks.tsv"):
        data = bytes.fromhex(row[5])
        ecc = bytes.fromhex(row[6])
        syn = rs_syndromes(data + ecc, len(ecc))
        assert all(s == 0 for s in syn), f"{row[:3]} nonzero syndromes {syn[:4]}"
        checked += 1
    assert checked >= 12


def test_gf_tables_are_consistent() -> None:
    """Verifier self-check: GF(256) invariants of the reference model itself."""
    assert GF_EXP[0] == 1 and GF_EXP[8] == 29
    for a, b in ((3, 7), (0x53, 0xCA), (2, 0x80)):
        assert gf_mul(a, b) == gf_mul(b, a)


# ---------------------------------------------------------------------------
# Interleave stage
# ---------------------------------------------------------------------------


def test_interleave_streams_match_reference() -> None:
    """interleave-streams must merge blocks round-robin per interleave-order.md."""
    run_pipeline()
    refs = public_refs()
    for row in read_tsv(STATE / "streams.tsv"):
        ref = refs[(row[0], row[1])]
        assert int(row[2]) == len(ref["interleaved"]), f"{row[:2]} stream length"
        assert row[3] == ref["interleaved"].hex(), f"{row[:2]} stream order"
        assert row[4] == ref["interleaved_sha256"], f"{row[:2]} stream digest"
        assert row[4] == hashlib.sha256(bytes.fromhex(row[3])).hexdigest()


def test_interleave_hidden_unequal_groups(tmp_path: Path) -> None:
    """Unequal group-2 tail codewords must stay column-interleaved per interleave-order.md."""
    inbox = write_hidden_inbox(tmp_path)
    run_pipeline(env={"TB3_SHIPBATCH_INBOX": str(inbox)})
    by_id = {p["payload_id"]: p for p in seeded_hidden_payloads()}
    rows = {row[1]: row for row in read_tsv(STATE / "streams.tsv")}
    unequal = 0
    for pid, payload in by_id.items():
        ref = encode_symbol(payload["text"], payload["ecc_level"])
        if ref["block_structure"]["group2_blocks"] >= 1:
            unequal += 1
        assert rows[pid][3] == ref["interleaved"].hex(), f"{pid} stream order"
    assert unequal >= 1


# ---------------------------------------------------------------------------
# Mask tournament stage
# ---------------------------------------------------------------------------


def test_tournament_penalties_match_reference() -> None:
    """All four penalty rules must score every mask per mask-tournament.md."""
    run_pipeline()
    refs = public_refs()
    grouped: dict[tuple[str, str], list[list[str]]] = {}
    for row in read_tsv(STATE / "tournament.tsv"):
        grouped.setdefault((row[0], row[1]), []).append(row)
    for key, ref in refs.items():
        rows = sorted(grouped[key], key=lambda r: int(r[2]))
        assert len(rows) == 8, f"{key} must score all eight masks"
        for row, want in zip(rows, ref["penalty_rows"]):
            assert int(row[2]) == want["mask_id"]
            assert int(row[3]) == want["penalty_runs"], f"{key} mask {row[2]} N1"
            assert int(row[4]) == want["penalty_blocks"], f"{key} mask {row[2]} N2"
            assert int(row[5]) == want["penalty_finder"], f"{key} mask {row[2]} N3"
            assert int(row[6]) == want["penalty_balance"], f"{key} mask {row[2]} N4"
            assert int(row[7]) == want["penalty_total"], f"{key} mask {row[2]} total"


def test_tournament_winner_is_lowest_total_lowest_mask() -> None:
    """Winner flag must mark the lowest-total, lowest-id mask per mask-tournament.md."""
    run_pipeline()
    refs = public_refs()
    grouped: dict[tuple[str, str], list[list[str]]] = {}
    for row in read_tsv(STATE / "tournament.tsv"):
        grouped.setdefault((row[0], row[1]), []).append(row)
    for key, ref in refs.items():
        winners = [int(r[2]) for r in grouped[key] if int(r[8]) == 1]
        assert winners == [ref["mask"]], f"{key} winning mask"


# ---------------------------------------------------------------------------
# Emit stage and manifest
# ---------------------------------------------------------------------------


def test_manifest_fields_match_reference() -> None:
    """Manifest fields must match independent recomputation per manifest-export.md."""
    run_pipeline()
    refs = public_refs()
    symbols = manifest_symbols()
    assert set(symbols) == set(refs)
    for key, ref in refs.items():
        sym = symbols[key]
        assert sym["version"] == ref["version"], f"{key} version"
        assert sym["size"] == symbol_size(ref["version"]), f"{key} size"
        assert sym["mask"] == ref["mask"], f"{key} mask"
        assert sym["total_bits"] == ref["plan"]["total_bits"], f"{key} total_bits"
        assert sym["segment_count"] == ref["plan"]["segment_count"], f"{key} segments"
        bs = ref["block_structure"]
        assert sym["ec_per_block"] == bs["ec_per_block"], f"{key} ec per block"
        assert sym["group1_blocks"] == bs["group1_blocks"], f"{key} g1 blocks"
        assert sym["group1_data_codewords"] == bs["group1_data_codewords"], f"{key} g1 data"
        assert sym["group2_blocks"] == bs["group2_blocks"], f"{key} g2 blocks"
        assert sym["group2_data_codewords"] == bs["group2_data_codewords"], f"{key} g2 data"
        assert sym["interleaved_sha256"] == ref["interleaved_sha256"], f"{key} stream digest"
        assert sym["matrix_sha256"] == ref["matrix_sha256"], f"{key} matrix digest"


def test_labels_decode_with_external_reader() -> None:
    """Every rendered label must decode to its exact payload text via zbar."""
    run_pipeline()
    payloads = {(p["batch_id"], p["payload_id"]): p for p in reference_payloads(PUBLIC_INBOX)}
    symbols = manifest_symbols()
    for key, sym in symbols.items():
        assert Path(sym["label_pgm"]).is_file(), f"{key} missing pgm"
        assert zbar_decode(sym["label_pgm"]) == payloads[key]["text"], f"{key} decode"


def test_hidden_labels_decode_with_external_reader(tmp_path: Path) -> None:
    """Verifier-generated batches must also decode exactly via zbar."""
    inbox = write_hidden_inbox(tmp_path)
    run_pipeline(env={"TB3_SHIPBATCH_INBOX": str(inbox)})
    by_id = {p["payload_id"]: p for p in seeded_hidden_payloads()}
    symbols = manifest_symbols()
    assert len(symbols) == len(by_id)
    for (batch_id, payload_id), sym in symbols.items():
        assert batch_id == "hx-901"
        assert zbar_decode(sym["label_pgm"]) == by_id[payload_id]["text"], f"{payload_id} decode"


def test_pgm_render_geometry() -> None:
    """PGM geometry must be (size + 2*quiet)*scale per manifest-export.md."""
    run_pipeline()
    refs = public_refs()
    symbols = manifest_symbols()
    key = min(refs)
    header = Path(symbols[key]["label_pgm"]).read_text(encoding="ascii").split("\n", 1)[0]
    fields = header.split()
    assert fields[0] == "P2"
    dim = (symbol_size(refs[key]["version"]) + 8) * 8
    assert int(fields[1]) == dim and int(fields[2]) == dim


def test_emit_reads_state_not_inbox(tmp_path: Path) -> None:
    """emit-labels must read persisted state only, ignoring inbox overrides."""
    run_pipeline()
    before = MANIFEST.read_bytes()
    empty = tmp_path / "empty-inbox"
    empty.mkdir()
    proc = run_cli("emit-labels", env={"TB3_SHIPBATCH_INBOX": str(empty)})
    assert proc.returncode == 0
    assert MANIFEST.read_bytes() == before


def test_pipeline_rerun_is_deterministic() -> None:
    """Repeated runs over unchanged inputs must be byte-identical."""
    run_pipeline()
    first_manifest = MANIFEST.read_bytes()
    first_streams = (STATE / "streams.tsv").read_bytes()
    run_pipeline()
    assert MANIFEST.read_bytes() == first_manifest
    assert (STATE / "streams.tsv").read_bytes() == first_streams


def test_reference_sha_helper_agrees_with_hashlib() -> None:
    """Verifier self-check: reference SHA-256 helper must agree with hashlib."""
    blob = b"qr-model2-cross-check"
    assert sha256_hex(blob) == hashlib.sha256(blob).hexdigest()


def test_ecc_block_table_integrity() -> None:
    """Verifier self-check: data + ecc codewords must fill each symbol exactly."""
    totals = {1: 26, 2: 44, 3: 70, 4: 100, 5: 134, 6: 172, 7: 196, 8: 242, 9: 292, 10: 346, 11: 404, 12: 466}
    for version, levels in ECC_BLOCKS.items():
        for spec in levels.values():
            ec, g1b, g1d, g2b, g2d = spec
            total = g1b * (g1d + ec) + g2b * (g2d + ec)
            assert total == totals[version], f"v{version} table row"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-rA"]))

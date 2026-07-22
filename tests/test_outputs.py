"""Behavioral checks for depctrl seal, cache, and reduce."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output"
REPORT = OUT / "constraint_report.json"
STAGING = OUT / "staging_report.json"
JOURNAL = OUT / "journal" / "lock.wal"
EVENTS = ENV / "data" / "events"
ACT = ENV / "data" / "act_map.json"
MH = EVENTS / "m_h.jsonl"
MA = EVENTS / "m_a.jsonl"
MB = EVENTS / "m_b.jsonl"
DEPCTRL = "/app/bin/depctrl"

# Fail fast offline: never hang waiting for a module proxy under allow_internet=false.
_GO_ENV = {
    **os.environ,
    "GOPROXY": "off",
    "GOSUMDB": "off",
    "GOTELEMETRY": "off",
    "GOTOOLCHAIN": "local",
}


def _hex16_of(pkg: str, dep: str, lo: str, hi: str, pre_tok: str, lift: bool) -> str:
    bit = 1 if lift else 0
    payload = f"{pkg}|{dep}|{lo}|{hi}|{pre_tok}|{bit}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _compile_bin() -> None:
    subprocess.run(
        ["go", "build", "-mod=readonly", "-o", "/app/bin/depctrl", "./cmd/depctrl"],
        cwd="/app/environment",
        check=True,
        env=_GO_ENV,
        timeout=90,
    )


def _wipe_out() -> None:
    for p in (OUT / "journal", OUT / "cache", OUT / "traces", OUT / "run_traces"):
        if p.exists():
            shutil.rmtree(p)
    for p in (REPORT, STAGING):
        if p.exists():
            p.unlink()


def _run_all() -> None:
    subprocess.run([DEPCTRL, "reconcile", "--all-mirrors"], check=True, timeout=60)


def _read_report() -> dict:
    assert REPORT.exists(), "missing constraint_report.json"
    return json.loads(REPORT.read_text())


def _index_dep(rows: list[dict]) -> dict[str, dict]:
    return {r["dep"]: r for r in rows}


def _dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _top_seq_lo(path: Path, dep: str) -> str:
    best_seq = -1
    lo = ""
    for row in _load_jsonl(path):
        if row.get("dep") != dep:
            continue
        seq = int(row.get("seq", 0))
        if seq >= best_seq:
            best_seq = seq
            lo = str(row.get("lo", ""))
    return lo


def _cap_hi(dep: str) -> str:
    for row in _load_jsonl(MH):
        if row.get("dep") == dep and row.get("lift") and row.get("peer_hi"):
            return str(row["peer_hi"])
    raise AssertionError(f"missing peer_hi for {dep}")


@pytest.fixture()
def built():
    _compile_bin()
    _wipe_out()
    yield
    _wipe_out()


def test_q_shape_hex(built):
    """Sealed report rows match the public schema and digest recipe."""
    _run_all()
    rows = _read_report()["rows"]
    assert len(rows) >= 2
    assert isinstance(rows, list)
    pkgs = {r["pkg"] for r in rows}
    assert "app" in pkgs
    assert REPORT.exists()
    assert JOURNAL.exists()
    for r in rows:
        for key in ("pkg", "dep", "lo", "hi", "pre_tok", "lift", "row_digest"):
            assert key in r
        assert type(r["lift"]) is bool
        assert isinstance(r["lo"], str) and isinstance(r["hi"], str)
        assert len(r["row_digest"]) == 16
        expect = _hex16_of(r["pkg"], r["dep"], r["lo"], r["hi"], r["pre_tok"], r["lift"])
        assert r["row_digest"] == expect
        assert r["pkg"]
        assert r["dep"]


def test_q_core_bound(built):
    """Required core-a edge survives seal with peer ceiling and allow token."""
    expect_lo = _top_seq_lo(MA, "core-a")
    expect_hi = _cap_hi("core-a")
    _run_all()
    core = _index_dep(_read_report()["rows"])["core-a"]
    assert core["pre_tok"] == "allow"
    assert core["lift"] is True
    assert core["lo"] == expect_lo
    assert core["hi"] == expect_hi
    assert core["pkg"] == "app"
    assert core["dep"] == "core-a"
    assert len(core["row_digest"]) == 16
    assert core["row_digest"] == _hex16_of(
        core["pkg"], core["dep"], core["lo"], core["hi"], core["pre_tok"], core["lift"]
    )
    assert expect_lo != ""
    assert expect_hi != ""


def test_q_opt_on(built):
    """Optional side-b appears when activation map enables k_x."""
    _run_all()
    rows = _read_report()["rows"]
    assert any(r.get("dep") == "side-b" for r in rows)
    side = _index_dep(rows)["side-b"]
    assert side["pkg"] == "app"
    assert isinstance(side["lo"], str)
    assert isinstance(side["hi"], str)
    assert side["dep"] == "side-b"
    expect = _hex16_of(
        side["pkg"], side["dep"], side["lo"], side["hi"], side["pre_tok"], side["lift"]
    )
    assert side["row_digest"] == expect
    assert len(side["row_digest"]) == 16
    assert "side-b" in {r["dep"] for r in rows}
    assert side["lo"] != ""
    assert side["hi"] != ""


def test_q_opt_off(built):
    """Disabling activation must drop side-b even after a warm cache."""
    _run_all()
    assert "side-b" in _index_dep(_read_report()["rows"])
    original = ACT.read_text()
    try:
        ACT.write_text(json.dumps({"k_x": False, "k_y": False}))
        _run_all()
        assert "side-b" not in _index_dep(_read_report()["rows"])
        assert "core-a" in _index_dep(_read_report()["rows"])
        assert REPORT.exists()
    finally:
        ACT.write_text(original)


def test_q_stale_cap(built):
    """Mutating peer_hi after a warm cache must change emitted hi."""
    _run_all()
    base_hi = _index_dep(_read_report()["rows"])["core-a"]["hi"]
    rows = _load_jsonl(MH)
    for r in rows:
        if r.get("dep") == "core-a" and r.get("lift"):
            r["peer_hi"] = "1.6.0"
    _dump_jsonl(MH, rows)
    try:
        _run_all()
        new_hi = _index_dep(_read_report()["rows"])["core-a"]["hi"]
        assert new_hi == _cap_hi("core-a")
        assert new_hi != base_hi
        assert isinstance(new_hi, str)
        assert new_hi != ""
    finally:
        for r in rows:
            if r.get("dep") == "core-a" and r.get("lift"):
                r["peer_hi"] = "1.9.0"
        _dump_jsonl(MH, rows)


def test_q_cap_raise(built):
    """Raising peer_hi above the intersection loosens the ceiling."""
    _run_all()
    base_hi = _index_dep(_read_report()["rows"])["core-a"]["hi"]
    rows = _load_jsonl(MH)
    raised = "9" + "".join(ch if ch == "." else "9" for ch in base_hi)
    for r in rows:
        if r.get("dep") == "core-a" and r.get("lift"):
            r["peer_hi"] = raised
    _dump_jsonl(MH, rows)
    try:
        _run_all()
        hi = _index_dep(_read_report()["rows"])["core-a"]["hi"]
        assert hi != base_hi
        assert hi != raised
        assert isinstance(hi, str)
        assert hi != ""
    finally:
        for r in rows:
            if r.get("dep") == "core-a" and r.get("lift"):
                r["peer_hi"] = "1.9.0"
        _dump_jsonl(MH, rows)


def test_q_seq_win(built):
    """Within one arm, highest seq feeds the sealed frame set."""
    original = MA.read_text()
    rows = _load_jsonl(MA)
    for r in rows:
        if r.get("dep") == "core-a" and r.get("seq") == 1:
            r["lo"] = "1.7.0"
            r["seq"] = 9
        elif r.get("dep") == "core-a" and r.get("seq") == 2:
            r["seq"] = 1
    _dump_jsonl(MA, rows)
    try:
        expect_lo = _top_seq_lo(MA, "core-a")
        _run_all()
        rows = _read_report()["rows"]
        core = _index_dep(rows)["core-a"]
        assert core["lo"] == expect_lo
        assert expect_lo != ""
        assert core["dep"] == "core-a"
        assert JOURNAL.exists()
    finally:
        MA.write_text(original)


def test_q_torn_crc(built):
    """A torn CRC line in the WAL must not poison the sealed fold."""
    _run_all()
    base = _index_dep(_read_report()["rows"])["core-a"]["hi"]
    JOURNAL.write_text(
        JOURNAL.read_text()
        + json.dumps(
            {
                "pkg": "app",
                "dep": "core-a",
                "lo": "9.9.9",
                "hi": "9.9.9",
                "pre_tok": "allow",
                "lift": True,
                "act_tok": "",
                "seq": 99,
                "epoch": 999,
                "crc": "00000000",
            }
        )
        + "\n"
    )
    _run_all()
    rows = _read_report()["rows"]
    core = _index_dep(rows)["core-a"]
    assert core["hi"] == base
    assert "core-a" in _index_dep(rows)
    assert core["pkg"] == "app"


def test_q_overwrite(built):
    """Static output file is overwritten by reconcile."""
    REPORT.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "pkg": "fake",
                        "dep": "x",
                        "lo": "0",
                        "hi": "0",
                        "pre_tok": "",
                        "lift": False,
                        "row_digest": "0" * 16,
                    }
                ]
            }
        )
    )
    _run_all()
    deps = {r["dep"] for r in _read_report()["rows"]}
    assert "core-a" in deps
    assert "x" not in deps
    assert len(_read_report()["rows"]) >= 1
    assert all(r.get("pkg") for r in _read_report()["rows"])


def test_q_status_trap(built):
    """status steady is not enough; reconcile still required for sealed report."""
    proc = subprocess.run(
        [DEPCTRL, "status"], check=True, capture_output=True, text=True, timeout=30
    )
    assert "steady" in proc.stdout
    if REPORT.exists():
        assert "core-a" not in REPORT.read_text()
    _run_all()
    assert "core-a" in _index_dep(_read_report()["rows"])
    assert REPORT.exists()
    assert JOURNAL.exists()


def test_q_cli_chain(built):
    """Manual collect -> reconcile -> emit still seals a terminal report."""
    subprocess.run([DEPCTRL, "collect"], check=True, timeout=60)
    subprocess.run([DEPCTRL, "reconcile"], check=True, timeout=60)
    staging = json.loads(STAGING.read_text())
    assert staging.get("partial") is True
    subprocess.run([DEPCTRL, "emit"], check=True, timeout=60)
    assert len(_read_report()["rows"]) >= 1
    assert REPORT.exists()
    assert "core-a" in _index_dep(_read_report()["rows"])


def test_q_flip_a(built):
    """Frontier A: highest-seq arm mutation must move sealed lo."""
    original = MA.read_text()
    rows = _load_jsonl(MA)
    baseline_lo = _top_seq_lo(MA, "core-a")
    bumped = baseline_lo.split(".")
    while len(bumped) < 3:
        bumped.append("0")
    bumped[1] = str(int(bumped[1]) + 3)
    new_lo = ".".join(bumped)
    for r in rows:
        if r.get("dep") == "core-a" and int(r.get("seq", 0)) == 2:
            r["lo"] = new_lo
    _dump_jsonl(MA, rows)
    try:
        expect_lo = _top_seq_lo(MA, "core-a")
        _run_all()
        core = _index_dep(_read_report()["rows"])["core-a"]
        assert core["lo"] == expect_lo
        assert expect_lo != baseline_lo
        assert expect_lo != ""
        assert JOURNAL.exists()
    finally:
        MA.write_text(original)


def test_q_flip_b(built):
    """Frontier B: warm cache must not resurrect side-b after activation clears."""
    _run_all()
    assert "side-b" in _index_dep(_read_report()["rows"])
    trace1 = json.loads((OUT / "traces" / "last_run.json").read_text())
    original = ACT.read_text()
    try:
        ACT.write_text(json.dumps({"k_x": False, "k_y": False}))
        _run_all()
        deps = _index_dep(_read_report()["rows"])
        assert "side-b" not in deps
        assert "core-a" in deps
        trace2 = json.loads((OUT / "traces" / "last_run.json").read_text())
        assert isinstance(trace2.get("cache_hit"), bool)
        assert trace1["row_n"] >= 2
        assert trace2["row_n"] >= 1
        assert trace2["row_n"] < trace1["row_n"]
    finally:
        ACT.write_text(original)


def test_q_flip_c(built):
    """Frontier C: double reconcile is idempotent on digests when inputs are fixed."""
    _run_all()
    first = _read_report()
    first_digests = sorted(r["row_digest"] for r in first["rows"])
    first_core = _index_dep(first["rows"])["core-a"]
    first_hi = first_core["hi"]
    _run_all()
    second = _read_report()
    second_core = _index_dep(second["rows"])["core-a"]
    assert sorted(r["row_digest"] for r in second["rows"]) == first_digests
    assert second_core["hi"] == first_hi
    assert first_hi == _cap_hi("core-a")
    assert (OUT / "traces" / "last_run.json").exists()


def test_q_arm_norm(built):
    """Cargo-style arm normalization drops -pre. when pre_tok is not allow."""
    _run_all()
    core = _index_dep(_read_report()["rows"])["core-a"]
    if core["pre_tok"] != "allow":
        assert "-pre." not in core["hi"]
    assert core["hi"] == _cap_hi("core-a")
    assert core["pkg"] == "app"
    assert isinstance(core["lift"], bool)
    _ = MB  # bundled arm-b witness remains part of the seal input set


def test_q_trace_last_run(built):
    """Trace sidecar records row and frame counts after a sealed run."""
    _compile_bin()
    _wipe_out()
    _run_all()
    trace = Path("/app/output/traces/last_run.json")
    assert trace.exists()
    payload = json.loads(trace.read_text())
    assert "row_n" in payload
    assert "frame_n" in payload
    assert payload["row_n"] >= 1
    assert payload["frame_n"] >= 1
    assert isinstance(payload.get("cache_hit"), bool)
    report_rows = _read_report()["rows"]
    assert payload["row_n"] == len(report_rows)
    assert payload["frame_n"] >= payload["row_n"]
    wal = Path("/app/output/journal/lock.wal")
    assert wal.exists()
    assert len(wal.read_text().splitlines()) >= 1
    assert all("row_digest" in r for r in report_rows)
    assert all(r.get("pkg") for r in report_rows)
    assert all(r.get("dep") for r in report_rows)
    assert isinstance(payload["row_n"], int)
    assert isinstance(payload["frame_n"], int)

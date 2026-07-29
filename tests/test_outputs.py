"""Held-out evaluation tests for k7_witness_report.json witness metrics."""

import hashlib
import json
import re
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

ENV_ROOT = "/app/environment"
OUT_PATH = "/app/output/k7_witness_report.json"
ENV = Path(ENV_ROOT)
K7_PROBE_PATH = "/opt/k7probe/dy"
W7_BIN = "/app/environment/bin/w7"
PACK = ENV / "bundle" / "k7" / "base.k7"
PAD = ENV / "bundle" / "k7" / "var089.pad"
WT_DIR = ENV / "data" / "wt_pair"
RETRY_SCHEDULES = ENV / "data" / "retry_schedules.json"
STAMP_RE = re.compile(r"stamp=([0-9a-f]{64})")
TESTS = Path(__file__).resolve().parent
SEALED_FOLD = json.loads(
    (TESTS / "data" / "sealed_metric_fold.json").read_text(encoding="utf-8")
)
BUNDLE_SHA = json.loads(
    (TESTS / "data" / "bundle_sha256.json").read_text(encoding="utf-8")
)


def tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + len(value).to_bytes(2, "big") + value


def frame(body: bytes) -> bytes:
    return b"K7FR" + len(body).to_bytes(4, "big") + body


def write_pack(path: Path, entries: list[tuple[str, bytes]]) -> None:
    buf = bytearray(b"K7PK")
    buf.extend(len(entries).to_bytes(4, "big"))
    for name, blob in entries:
        nb = name.encode()
        buf.extend(len(nb).to_bytes(4, "big"))
        buf.extend(nb)
        buf.extend(len(blob).to_bytes(4, "big"))
        buf.extend(blob)
    path.write_bytes(bytes(buf))


@contextmanager
def replace_file(path: Path, data: bytes):
    original = path.read_bytes()
    path.write_bytes(data)
    try:
        yield
    finally:
        path.write_bytes(original)


@contextmanager
def replace_witness_dir(files: dict[str, str]):
    originals = {p.name: p.read_text() for p in WT_DIR.glob("*.json")}
    for existing in WT_DIR.glob("*.json"):
        existing.unlink()
    for name, data in files.items():
        (WT_DIR / name).write_text(data)
    try:
        yield
    finally:
        for existing in WT_DIR.glob("*.json"):
            existing.unlink()
        for name, data in originals.items():
            (WT_DIR / name).write_text(data)


def pack_capture_names() -> list[str]:
    data = PACK.read_bytes()
    assert data[:4] == b"K7PK"
    pos = 8
    count = int.from_bytes(data[4:8], "big")
    names: list[str] = []
    for _ in range(count):
        nl = int.from_bytes(data[pos : pos + 4], "big")
        pos += 4
        name = data[pos : pos + nl].decode()
        pos += nl
        bl = int.from_bytes(data[pos : pos + 4], "big")
        pos += 4 + bl
        names.append(name)
    return sorted(names)


def capture_name(index: int) -> str:
    return pack_capture_names()[index]


def sidecar_capture_key(path: Path) -> str | None:
    stem = path.stem
    m = re.match(r"^\d+-(.+)$", stem)
    if m:
        return m.group(1)
    return None


def witness_for_capture(capture: str) -> dict:
    files = sorted((ENV / "data/wt_pair").glob("*.json"))
    for path in files:
        key = sidecar_capture_key(path)
        if key is not None and key == capture:
            return json.loads(path.read_text())[0]
    idx = pack_capture_names().index(capture)
    assert idx < len(files)
    return json.loads(files[idx].read_text())[0]


def frame_body(frame: bytes) -> bytes:
    blen = int.from_bytes(frame[6:8], "big")
    return frame[8 : 8 + blen]


def top_level_tags(frame: bytes) -> list[int]:
    return [tag for tag, _ in top_level_chunks(frame)]


def top_level_chunks(frame: bytes) -> list[tuple[int, bytes]]:
    body = frame_body(frame)
    chunks: list[tuple[int, bytes]] = []
    pos = 0
    while pos + 3 <= len(body):
        tag = body[pos]
        ln = int.from_bytes(body[pos + 1 : pos + 3], "big")
        pos += 3
        if pos + ln > len(body):
            break
        value = body[pos : pos + ln]
        pos += ln
        if tag != 0x00:
            chunks.append((tag, value))
    return chunks


def pack_get(name: str) -> bytes:
    data = PACK.read_bytes()
    assert data[:4] == b"K7PK"
    pos = 8
    count = int.from_bytes(data[4:8], "big")
    for _ in range(count):
        nl = int.from_bytes(data[pos : pos + 4], "big")
        pos += 4
        entry = data[pos : pos + nl].decode()
        pos += nl
        bl = int.from_bytes(data[pos : pos + 4], "big")
        pos += 4
        blob = data[pos : pos + bl]
        pos += bl
        if entry == name:
            return blob
    raise KeyError(name)


def dy_observe(frame: bytes) -> dict:
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(frame)
        path = tf.name
    try:
        proc = subprocess.run(
            [K7_PROBE_PATH, "observe", "--chunk", path],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)
    finally:
        Path(path).unlink(missing_ok=True)


def run_emit() -> dict:
    out = Path(OUT_PATH)
    if out.exists():
        out.unlink()
    subprocess.run(
        [W7_BIN, "emit", "--out", OUT_PATH],
        check=True,
        cwd=ENV_ROOT,
    )
    return json.loads(out.read_text())


def stamp_from_rationale(text: str) -> str:
    match = STAMP_RE.search(text)
    assert match, f"missing stamp= digest in {text!r}"
    return match.group(1)


def pack_entry_count() -> int:
    data = PACK.read_bytes()
    return int.from_bytes(data[4:8], "big")


def metric_fold_digest(doc: dict, pack_count: int) -> str:
    parts: list[str] = []
    lrows = sorted(
        (ln for ln in doc["lines"] if ln["line_id"].startswith("L-")),
        key=lambda ln: ln["line_id"],
    )
    for ln in lrows:
        stamp = stamp_from_rationale(ln["rationale_text"])
        parts.append(f"{ln['line_id']}|{ln['scope_code']}|{ln['timing_anchor']}|{stamp}")
    rrows = sorted(
        (ln for ln in doc["lines"] if ln["line_id"].startswith("R-")),
        key=lambda ln: ln["line_id"],
    )
    for ln in rrows:
        parts.append(f"{ln['line_id']}|{ln['transition_id']}")
    parts.append(f"pack:{pack_count}")
    payload = "\n".join(parts)
    mask64 = (1 << 64) - 1
    total = 0
    for i, ch in enumerate(payload):
        total = (total + ((i + 1) * ord(ch))) & mask64
    return f"{total & 0xFFFFFFFF:08x}"


def line_for(doc: dict, line_id: str) -> dict:
    return next(ln for ln in doc["lines"] if ln["line_id"] == line_id)


def line_for_capture(doc: dict, capture: str) -> dict:
    return line_for(doc, f"L-{capture}")


@pytest.fixture(scope="session")
def built_w7() -> None:
    w7_path = ENV / "bin" / "w7"
    if not w7_path.is_file():
        proc = subprocess.run(
            ["make", "-C", ENV_ROOT, "build"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
    assert w7_path.is_file()


def test_r1_canon(built_w7: None) -> None:
    """First pack capture: rationale stamp must match live probe canon_hex on the frame."""
    capture = capture_name(0)
    frame = pack_get(capture)
    obs = dy_observe(frame)
    doc = run_emit()
    line = line_for_capture(doc, capture)
    assert stamp_from_rationale(line["rationale_text"]) == obs["canon_hex"]


def test_r2_part(built_w7: None) -> None:
    """Partitioned frame delivery matches one-shot stamp in report rationale."""
    capture = capture_name(1)
    frame = pack_get(capture)
    obs_full = dy_observe(frame)
    half = len(frame) // 2
    obs_part = dy_observe(frame[:half] + frame[half:])
    assert obs_full["canon_hex"] == obs_part["canon_hex"]
    doc = run_emit()
    line = line_for_capture(doc, capture)
    assert stamp_from_rationale(line["rationale_text"]) == obs_full["canon_hex"]


def test_r3_alt(built_w7: None) -> None:
    """Second pack row scope matches witness expectation."""
    capture = capture_name(1)
    doc = run_emit()
    line = line_for_capture(doc, capture)
    witness = witness_for_capture(capture)
    assert line["scope_code"] == witness["scope_expect"]


def test_r4_usage(built_w7: None) -> None:
    """First pack row scope matches witness expectation."""
    capture = capture_name(0)
    doc = run_emit()
    line = line_for_capture(doc, capture)
    witness = witness_for_capture(capture)
    assert line["scope_code"] == witness["scope_expect"]


def test_r5_once(built_w7: None) -> None:
    """Distinct retry transition ids each appear once among R- rows."""
    doc = run_emit()
    retry = [ln for ln in doc["lines"] if ln["line_id"].startswith("R-")]
    assert len(retry) == 2


def test_r6_dup(built_w7: None) -> None:
    """Duplicate transition id in schedule appears once."""
    doc = run_emit()
    sched = json.loads((ENV / "data/retry_schedules.json").read_text())
    tid = sched["steps"][0]["transition_id"]
    ids = [ln["transition_id"] for ln in doc["lines"] if ln["line_id"].startswith("R-")]
    assert sum(1 for x in ids if x == tid) == 1


def test_r7_anchor(built_w7: None) -> None:
    """Timing anchor uses min(ds_inception, cert_not_before) from COLS.md."""
    doc = run_emit()
    first = capture_name(0)
    wf = witness_for_capture(first)
    first_line = line_for_capture(doc, first)
    assert first_line["timing_anchor"] == min(wf["ds_inception"], wf["cert_not_before"])
    second = capture_name(1)
    ws = witness_for_capture(second)
    second_line = line_for_capture(doc, second)
    assert second_line["timing_anchor"] == min(ws["ds_inception"], ws["cert_not_before"])


def test_r8_wt(built_w7: None) -> None:
    """Witness tables produce one report line per pack entry."""
    doc = run_emit()
    pack_lines = [ln for ln in doc["lines"] if ln["line_id"].startswith("L-")]
    data = PACK.read_bytes()
    count = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7]
    assert len(pack_lines) == count


def test_r9_pad(built_w7: None) -> None:
    """Padded capture lane: filler bytes must not change the canonical stamp vs dy observe."""
    frame = PAD.read_bytes()
    obs = dy_observe(frame)
    doc = run_emit()
    line = line_for_capture(doc, capture_name(1))
    assert stamp_from_rationale(line["rationale_text"]) == obs["canon_hex"]


def test_r10_iface(built_w7: None) -> None:
    """w7 CLI help documents the emit subcommand agents use for witness-metrics JSON."""
    proc = subprocess.run(
        [W7_BIN],
        capture_output=True,
        text=True,
        cwd=ENV_ROOT,
        check=False,
    )
    assert "emit" in proc.stdout


def test_r11_gamma_scope(built_w7: None) -> None:
    """Third pack row scope matches its witness sidecar."""
    capture = capture_name(2)
    doc = run_emit()
    line = line_for_capture(doc, capture)
    witness = witness_for_capture(capture)
    assert line["scope_code"] == witness["scope_expect"]


def test_r12_gamma_anchor(built_w7: None) -> None:
    """Third pack row timing anchor uses min witness fields."""
    capture = capture_name(2)
    doc = run_emit()
    line = line_for_capture(doc, capture)
    witness = witness_for_capture(capture)
    assert line["timing_anchor"] == min(witness["ds_inception"], witness["cert_not_before"])


def test_r13_gamma_stamp(built_w7: None) -> None:
    """Third pack row rationale embeds exact instrument stamp for its frame."""
    capture = capture_name(2)
    frame = pack_get(capture)
    obs = dy_observe(frame)
    doc = run_emit()
    line = line_for_capture(doc, capture)
    assert stamp_from_rationale(line["rationale_text"]) == obs["canon_hex"]


def test_r14_retry_second(built_w7: None) -> None:
    """Second scheduled transition id appears among retry rows."""
    doc = run_emit()
    sched = json.loads((ENV / "data/retry_schedules.json").read_text())
    tid2 = sched["steps"][2]["transition_id"]
    ids = {ln["transition_id"] for ln in doc["lines"] if ln["line_id"].startswith("R-")}
    assert tid2 in ids


def test_r15_sidecar_order(built_w7: None) -> None:
    """Renamed wt_pair files with numeric prefixes still join the matching capture by name."""
    capture = capture_name(2)
    doc = run_emit()
    line = line_for_capture(doc, capture)
    witness = witness_for_capture(capture)
    assert line["scope_code"] == witness["scope_expect"]
    assert line["timing_anchor"] == min(witness["ds_inception"], witness["cert_not_before"])


def test_r17_gamma_last_alt_ssh(built_w7: None) -> None:
    """When DNS and SSH alternates stack, last wire-order alternate sets scope."""
    capture = capture_name(2)
    doc = run_emit()
    line = line_for_capture(doc, capture)
    witness = witness_for_capture(capture)
    tags = top_level_tags(pack_get(capture))
    assert tags[0] != tags[-1]
    assert line["scope_code"] == witness["scope_expect"]


def test_r18_altpack(built_w7: None) -> None:
    """Synthetic four-entry pack with prefixed sidecars: joins witnesses by capture name (not
    positional index), preserves scope, timing_anchor, and instrument-coupled stamps for novel
    rows including a suffixed alternate capture."""
    first = capture_name(0)
    second = capture_name(1)
    third = capture_name(2)
    extra = f"{third}-alt"
    first_blob = pack_get(first)
    second_blob = pack_get(second)
    third_blob = pack_get(third)
    second_chunks = top_level_chunks(second_blob)
    dns_value = next(value for tag, value in second_chunks if tag == 0x10)
    ssh_value = next(value for tag, value in second_chunks if tag == 0x11)
    usage_value = next(value for tag, value in second_chunks if tag == 0x20)
    extra_body = tlv(0x11, ssh_value)
    extra_body += tlv(0x10, dns_value)
    extra_body += tlv(0x20, usage_value)
    extra_blob = frame(extra_body)
    pack_rows = [
        (third, third_blob),
        (extra, extra_blob),
        (second, second_blob),
        (first, first_blob),
    ]
    witness_files = {
        f"10-{first}.json": json.dumps(
            [{"cert_not_before": 205, "ds_inception": 95, "scope_expect": "ssh"}]
        ),
        f"20-{second}.json": json.dumps(
            [{"cert_not_before": 190, "ds_inception": 160, "scope_expect": "ssh"}]
        ),
        f"30-{third}.json": json.dumps(
            [{"cert_not_before": 255, "ds_inception": 310, "scope_expect": "ssh"}]
        ),
        f"40-{extra}.json": json.dumps(
            [{"cert_not_before": 340, "ds_inception": 410, "scope_expect": "dns"}]
        ),
    }
    with replace_file(
        PACK,
        b"",
    ):
        write_pack(PACK, pack_rows)
        with replace_witness_dir(witness_files):
            doc = run_emit()
    line_ids = {line["line_id"] for line in doc["lines"]}
    assert {f"L-{name}" for name, _ in pack_rows} <= line_ids
    extra_line = line_for_capture(doc, extra)
    extra_witness = json.loads(witness_files[f"40-{extra}.json"])[0]
    assert extra_line["scope_code"] == extra_witness["scope_expect"]
    assert extra_line["timing_anchor"] == min(
        extra_witness["ds_inception"], extra_witness["cert_not_before"]
    )
    assert stamp_from_rationale(extra_line["rationale_text"]) == dy_observe(extra_blob)["canon_hex"]
    first_line = line_for_capture(doc, first)
    first_witness = json.loads(witness_files[f"10-{first}.json"])[0]
    third_line = line_for_capture(doc, third)
    third_witness = json.loads(witness_files[f"30-{third}.json"])[0]
    assert first_line["timing_anchor"] == min(
        first_witness["ds_inception"], first_witness["cert_not_before"]
    )
    assert third_line["timing_anchor"] == min(
        third_witness["ds_inception"], third_witness["cert_not_before"]
    )


def test_r19_retry_tid_canonical(built_w7: None) -> None:
    """Retry rows dedupe by transition_id even if schedule repeats across epochs."""
    shared_id = f"retry-{capture_name(0)}"
    unique_id = f"retry-{capture_name(2)}"
    sched = {
        "steps": [
            {"frame": capture_name(0), "epoch": 1, "transition_id": shared_id},
            {"frame": capture_name(1), "epoch": 2, "transition_id": shared_id},
            {"frame": capture_name(2), "epoch": 3, "transition_id": unique_id},
        ]
    }
    with replace_file(RETRY_SCHEDULES, bytes(json.dumps(sched), "utf-8")):
        doc = run_emit()
    ids = [ln["transition_id"] for ln in doc["lines"] if ln["line_id"].startswith("R-")]
    assert ids.count(shared_id) == 1
    assert ids.count(unique_id) == 1


def test_r20_metric_fold_sealed(built_w7: None) -> None:
    """metric_fold must match verifier-sealed cascade on the canonical pack."""
    doc = run_emit()
    assert doc.get("metric_fold") == SEALED_FOLD["metric_fold"]


def test_r21_metric_fold_recomputes(built_w7: None) -> None:
    """metric_fold must bind L-rows, R-rows, and pack entry count."""
    doc = run_emit()
    expect = metric_fold_digest(doc, pack_entry_count())
    assert doc.get("metric_fold") == expect


def test_r22_metric_fold_stable_on_repeat_emit(built_w7: None) -> None:
    """Repeated emit on unchanged inputs must reproduce the same metric_fold."""
    first = run_emit()
    second = run_emit()
    assert first["metric_fold"] == second["metric_fold"]
    assert first["metric_fold"] == metric_fold_digest(second, pack_entry_count())


def test_k7_bundle_bytes_immutable(built_w7: None) -> None:
    """Sealed pack bytes under bundle/k7 must not be edited to pass evaluation."""
    for rel, expect in BUNDLE_SHA.items():
        path = ENV / rel
        assert path.is_file(), rel
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == expect, f"{rel} sha256 mismatch"


def test_k7_l_rows_lex_sorted(built_w7: None) -> None:
    """L-* rows must follow lexicographic capture order per MODEL.contract."""
    doc = run_emit()
    l_ids = [ln["line_id"] for ln in doc["lines"] if ln["line_id"].startswith("L-")]
    captures = [lid[2:] for lid in l_ids]
    assert captures == sorted(captures)
    assert captures == sorted(pack_capture_names())


def test_k7_full_pack_instrument_witness_coupling(built_w7: None) -> None:
    """Every pack capture: scope, anchor, and stamp must agree with sidecar and dy."""
    doc = run_emit()
    for capture in pack_capture_names():
        frame = pack_get(capture)
        obs = dy_observe(frame)
        line = line_for_capture(doc, capture)
        witness = witness_for_capture(capture)
        assert line["scope_code"] == witness["scope_expect"], capture
        assert line["timing_anchor"] == min(
            witness["ds_inception"], witness["cert_not_before"]
        ), capture
        assert stamp_from_rationale(line["rationale_text"]) == obs["canon_hex"], capture

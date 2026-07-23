"""Domain checks for icing formal witness bundle regeneration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output/k_out.json")
SITE_ROOT = ENV / "k8"


def _sha256_hex(data: bytes) -> str:
    proc = subprocess.run(
        ["sha256sum"],
        input=data,
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode().split()[0]


def _mode_digest(mode: bytes) -> str:
    return _sha256_hex(mode)[:8]


def _parse_ber_rows(buf: bytes) -> list[tuple[int, int, bytes]]:
    body = buf
    if len(buf) >= 4 and buf[0] == 0x30 and buf[1] == 0x80:
        body = buf[2:-2]
    rows: list[tuple[int, int, bytes]] = []
    i = 0
    while i + 2 < len(body):
        if body[i] != 0x30:
            i += 1
            continue
        ln = body[i + 1]
        chunk = body[i + 2 : i + 2 + ln]
        arm = weight = 0
        mode = b""
        j = 0
        ints: list[int] = []
        while j + 2 <= len(chunk):
            tag = chunk[j]
            vlen = chunk[j + 1]
            val = chunk[j + 2 : j + 2 + vlen]
            if tag == 0x02 and val:
                ints.append(val[0])
            elif tag == 0x04:
                mode = bytes(val)
            j += 2 + vlen
        if len(ints) >= 2:
            arm, weight = ints[0], ints[1]
        if mode:
            rows.append((arm, weight, mode))
        i += 2 + ln
    return rows


def _canon_fold_digest(rows: list[tuple[int, int, bytes]]) -> str:
    keyed = sorted((a, _mode_digest(m), w) for a, w, m in rows)
    joined = "\n".join(f"{a}|{md}|{w}" for a, md, w in keyed)
    return _sha256_hex(joined.encode())


def _score_rows(rows: list[tuple[int, int, bytes]], eta: float) -> dict[str, int]:
    obs: dict[str, int] = {}
    for arm, weight, _ in rows:
        w_prev = float(weight)
        w_next = w_prev * pow(2.718281828, -eta * w_prev / 100.0)
        obs[str(arm)] = int(round(w_next / 10.0))
    return obs


def _read_sched(site: str) -> tuple[float, int, float]:
    lines = (SITE_ROOT / site / "schedule.tsv").read_text().splitlines()
    row = lines[1].split("\t")
    return float(row[2]), int(row[1]), float(row[3])


def _catalog_digest() -> str:
    proc = subprocess.run(
        [
            "sqlite3",
            str(ENV / "var/k9.db"),
            "SELECT arm_id || '|' || mode_tag || '|' || lineage_seq || '|' || weight_base "
            "FROM arm_lineage ORDER BY arm_id, mode_tag",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    joined = proc.stdout.strip()
    return _sha256_hex(joined.encode())


def _closed_keys() -> set[tuple[int, str]]:
    proc = subprocess.run(
        ["sqlite3", str(ENV / "var/k9.db"), "SELECT arm_id, mode_tag FROM arm_lineage"],
        capture_output=True,
        text=True,
        check=True,
    )
    keys: set[tuple[int, str]] = set()
    for line in proc.stdout.strip().splitlines():
        arm_s, mode = line.split("|", 1)
        keys.add((int(arm_s), _mode_digest(mode.encode())))
    return keys


def _obligation_count(rows: list[tuple[int, int, bytes]]) -> int:
    closed = _closed_keys()
    return sum(1 for a, _, m in rows if (a, _mode_digest(m)) not in closed)


def _apply_perm(rows: list[tuple[int, int, bytes]], perm: list[int]) -> list[tuple[int, int, bytes]]:
    if len(perm) != len(rows):
        return list(rows)
    return [rows[i] for i in perm]


def _regen() -> dict:
    if OUT.exists():
        OUT.unlink()
    subprocess.run(
        [
            "/app/environment/exec/k_run.sh",
            "--site-root",
            "/app/environment/k8",
            "--out",
            "/app/output/k_out.json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(OUT.read_text(encoding="utf-8"))


@pytest.fixture(scope="session", autouse=True)
def _bundle():
    data = _regen()
    assert OUT.exists()
    return data


def _site(bundle: dict, site_id: str) -> dict:
    for s in bundle["sites"]:
        if s["site_id"] == site_id:
            return s
    raise KeyError(site_id)


def test_m7_closed_zero(_bundle):
    """Closed site packs show zero catalog obligation violations after regen."""
    for site in ("s01", "s02", "s03"):
        rows = _parse_ber_rows((SITE_ROOT / site / "xslice.bin").read_bytes())
        assert _site(_bundle, site)["obligation_count"] == _obligation_count(rows)


def test_h4_env_hold(_bundle):
    """Synth arm score observations stay within certified envelope caps."""
    for site in ("s01", "s02", "s03"):
        _, _, env_hi = _read_sched(site)
        srec = _site(_bundle, site)
        cap = int(round(env_hi * 10.0))
        for val in srec["synth_obs"].values():
            assert int(val) <= cap


def test_n2_fold_stable(_bundle):
    """Fold digest is stable under annex presentation permutations."""
    for site in ("s01", "s02", "s03"):
        base = _parse_ber_rows((SITE_ROOT / site / "xslice.bin").read_bytes())
        for orb_path in sorted((SITE_ROOT / "_orbits").glob("*.json")):
            spec = json.loads(orb_path.read_text())
            if spec.get("site") != site:
                continue
            permuted = _apply_perm(base, spec["perm"])
            expected = _canon_fold_digest(permuted)
            assert _site(_bundle, site)["fold_digest"] == expected


def test_j9_perm_stable(_bundle):
    """Admission label does not flip when annex rows are permuted."""
    for site in ("s01", "s02", "s03"):
        eta, threshold, _ = _read_sched(site)
        base = _parse_ber_rows((SITE_ROOT / site / "xslice.bin").read_bytes())
        obs = _score_rows(base, eta)
        adm = "open" if max(obs.values(), default=0) >= threshold else "hold"
        for orb_path in sorted((SITE_ROOT / "_orbits").glob("*.json")):
            spec = json.loads(orb_path.read_text())
            if spec.get("site") != site:
                continue
            permuted = _apply_perm(base, spec["perm"])
            obs2 = _score_rows(permuted, eta)
            adm2 = "open" if max(obs2.values(), default=0) >= threshold else "hold"
            assert adm2 == adm
        assert _site(_bundle, site)["admission"] == adm


def test_p4_path_hold(_bundle):
    """Stress path peaks stay inside site certified envelopes."""
    for rec in _bundle["stress"]:
        _, _, env_hi = _read_sched(rec["site_id"])
        assert float(rec["path_peak"]) <= env_hi + 1e-9


def test_z5_emit_shape(_bundle):
    """Regenerated bundle matches schema, digests, and is byte-stable across runs."""
    required_site = {
        "site_id",
        "obligation_count",
        "env_hi",
        "synth_obs",
        "fold_digest",
        "catalog_digest",
        "admission",
        "reach_obs",
    }
    required_stress = {"stress_id", "site_id", "path_peak"}
    assert _bundle["schema_version"] == 1
    assert len(_bundle["sites"]) == 3
    assert len(_bundle["lineage_rows"]) >= 5
    for site in _bundle["sites"]:
        for key in required_site:
            assert key in site
        assert len(site["fold_digest"]) == 64
        assert site["catalog_digest"] == _catalog_digest()
    for rec in _bundle["stress"]:
        for key in required_stress:
            assert key in rec
    if OUT.exists():
        OUT.unlink()
    subprocess.run(
        [
            "/app/environment/exec/k_run.sh",
            "--site-root",
            "/app/environment/k8",
            "--out",
            "/app/output/k_out.json",
        ],
        check=True,
    )
    second = json.loads(OUT.read_text())
    assert second == _bundle

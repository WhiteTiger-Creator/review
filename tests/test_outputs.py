"""Black-box verifier for trust-store DB remediation artifacts.

Invokes /app/trust-remediator/build/trust_attest on the shipped incident bundle
and on mutated copies of it. Expected output is re-derived independently in
Python from operator handbook rules.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import io
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import ExtensionOID, NameOID

DATA_DIR = Path("/app/data")
OUT_DIR = Path("/app/output")
PROJECT_DIR = Path("/app/trust-remediator")
BIN_PATH = PROJECT_DIR / "build" / "trust_attest"

FP_RE = re.compile(r"^[0-9a-f]{64}$")
REASONS = {"valid", "bad_signature", "no_path", "revoked", "name_constraint",
           "expired", "not_yet_valid"}
RANK = {"acceptable": 0, "not_yet_valid": 1, "expired": 2, "name_constraint": 3, "revoked": 4}


def access_minute(ts: str) -> str:
    return ts[:16]


def join_key(cert_fp: str, service_id: str, access_ts: str) -> str:
    raw = f"{cert_fp}:{service_id}:{access_minute(access_ts)}".encode()
    return hashlib.sha256(raw).hexdigest()


def artifact_digest(sql: str, access_tsv: str, cert_tsv: str) -> str:
    h = hashlib.sha256()
    h.update(sql.encode())
    h.update(access_tsv.encode())
    h.update(cert_tsv.encode())
    return h.hexdigest()


def _fp(c: x509.Certificate) -> str:
    return hashlib.sha256(c.public_bytes(Encoding.DER)).hexdigest()


def _cn(c: x509.Certificate) -> str:
    return c.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value


def _load_pems(sub: str, data_dir: Path) -> list[x509.Certificate]:
    return [
        x509.load_pem_x509_certificate(Path(f).read_bytes())
        for f in sorted(glob.glob(str(data_dir / sub / "*.pem")))
    ]


def _verify(child: x509.Certificate, parent: x509.Certificate) -> bool:
    try:
        parent.public_key().verify(
            child.signature, child.tbs_certificate_bytes,
            padding.PKCS1v15(), child.signature_hash_algorithm)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _self_signed(c: x509.Certificate) -> bool:
    return c.subject.public_bytes() == c.issuer.public_bytes() and _verify(c, c)


def _dns_sans(c: x509.Certificate) -> list[str]:
    try:
        ext = c.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        return list(ext.get_values_for_type(x509.DNSName))
    except x509.ExtensionNotFound:
        return []


def _name_constraints(c: x509.Certificate) -> tuple[list[str], list[str]]:
    try:
        nc = c.extensions.get_extension_for_oid(ExtensionOID.NAME_CONSTRAINTS).value
    except x509.ExtensionNotFound:
        return [], []
    permitted = [g.value for g in (nc.permitted_subtrees or []) if isinstance(g, x509.DNSName)]
    excluded = [g.value for g in (nc.excluded_subtrees or []) if isinstance(g, x509.DNSName)]
    return permitted, excluded


def _dns_match(entry: str, dns: str) -> bool:
    return dns == entry or dns.endswith("." + entry)


def load_post_distrust(data_dir: Path) -> dict[str, list[str]]:
    conn = sqlite3.connect(data_dir / "trust_store.db")
    fps = [r[0] for r in conn.execute(
        "SELECT fingerprint FROM distrust_fingerprint ORDER BY fingerprint")]
    names = [r[0] for r in conn.execute(
        "SELECT common_name FROM distrust_name ORDER BY common_name")]
    conn.close()
    return {"by_fingerprint": fps, "by_name": names}


def load_trusted(data_dir: Path) -> set[str]:
    conn = sqlite3.connect(data_dir / "trust_store.db")
    trusted = {r[0] for r in conn.execute("SELECT fingerprint FROM trusted_roots")}
    conn.close()
    return trusted


def policy_warrant_quorum(data_dir: Path) -> int:
    """Read warrant_quorum out of the [remediation] section."""
    section = ""
    for raw in (data_dir / "remediation.policy").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "remediation" or "=" not in line:
            continue
        key, val = line.split("=", 1)
        if key.strip() == "warrant_quorum":
            return int(val.strip())
    return 1


def authority_common_names(data_dir: Path) -> set[str]:
    names: set[str] = set()
    for pem in sorted((data_dir / "authorities").glob("*.pem")):
        cert = x509.load_pem_x509_certificate(pem.read_bytes())
        names.add(cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value)
    return names


def build_warrant_patch(
    data_dir: Path, base: dict[str, list[str]]
) -> tuple[dict[str, list[str]], dict[str, Any], str]:
    """Independently re-derive the honouring decision for every warrant.

    Each warrant is judged on its own against the post-migration store; nothing
    here depends on the order rows come back in.
    """
    conn = sqlite3.connect(data_dir / "warrants" / "warrants.db")
    warrants = conn.execute(
        "SELECT warrant_id, target_kind, target_value, issuer_cn, not_before, not_after "
        "FROM distrust_warrant ORDER BY warrant_id ASC"
    ).fetchall()
    custodians = {
        r[0]
        for r in conn.execute(
            "SELECT signer_id FROM authorized_signer WHERE role = 'custodian'"
        )
    }
    signers: dict[str, set[str]] = {}
    for wid, signer in conn.execute(
        "SELECT warrant_id, signer_id FROM warrant_countersignature"
    ):
        signers.setdefault(wid, set()).add(signer)
    countermanded = {
        r[0] for r in conn.execute("SELECT warrant_id FROM warrant_countermand")
    }
    conn.close()

    quorum = policy_warrant_quorum(data_dir)
    eval_time = (data_dir / "eval_time.txt").read_text().strip()
    authorities = authority_common_names(data_dir)
    base_names = set(base["by_name"])

    fp_set = set(base["by_fingerprint"])
    name_set = set(base["by_name"])
    post_set = set(base["by_fingerprint"])
    honored = inert = 0
    stmts = ["-- trust store remediation patch"]

    for wid, kind, value, issuer, not_before, not_after in warrants:
        endorsements = len(signers.get(wid, set()) & custodians)
        eligible = (
            kind in ("fingerprint", "common_name")
            and not_before <= eval_time <= not_after
            and endorsements >= quorum
            and wid not in countermanded
            and issuer in authorities
            and issuer not in base_names
        )
        if not eligible:
            inert += 1
            continue
        honored += 1
        if kind == "fingerprint":
            fp_set.add(value)
            stmts.append(
                "INSERT OR IGNORE INTO distrust_fingerprint (fingerprint, source) "
                f"VALUES ('{value}', 'warrant_honored');"
            )
        else:
            name_set.add(value)
            stmts.append(
                "INSERT OR IGNORE INTO distrust_name (common_name, source) "
                f"VALUES ('{value}', 'warrant_honored');"
            )

    summary = {
        "warrants_honored": honored,
        "warrants_inert": inert,
        "restored_fingerprints": sorted(fp_set - post_set),
    }
    sql = "\n".join(stmts) + "\n"
    return {"by_fingerprint": sorted(fp_set), "by_name": sorted(name_set)}, summary, sql


def parse_journal(data_dir: Path) -> list[dict[str, str]]:
    recs: list[dict[str, str]] = []
    for line in (data_dir / "access" / "access.journal").read_text().splitlines():
        line = line.strip()
        if not line.startswith("ACCESS"):
            continue
        kv: dict[str, str] = {}
        for part in line.split()[1:]:
            if "=" in part:
                k, v = part.split("=", 1)
                kv[k] = v
        recs.append({"cert_fp": kv["cert_fp"], "service_id": kv["service"], "access_ts": kv["ts"]})
    return recs


def build_access_evidence(data_dir: Path) -> str:
    fs_recs = parse_journal(data_dir)
    conn = sqlite3.connect(data_dir / "access" / "access_audit.db")
    db_recs = [
        {"cert_fp": r[0], "service_id": r[1], "access_ts": r[2]}
        for r in conn.execute("SELECT cert_fp, service_id, access_ts FROM access_records")
    ]
    conn.close()
    fs_keys: dict[tuple[str, str, str], str] = {}
    db_keys: dict[tuple[str, str, str], str] = {}
    for r in fs_recs:
        minute = access_minute(r["access_ts"])
        t = (r["cert_fp"], r["service_id"], minute)
        fs_keys[t] = join_key(r["cert_fp"], r["service_id"], r["access_ts"])
    for r in db_recs:
        minute = access_minute(r["access_ts"])
        t = (r["cert_fp"], r["service_id"], minute)
        db_keys[t] = join_key(r["cert_fp"], r["service_id"], r["access_ts"])
    rows: list[list[str]] = []
    for cert_fp, svc, minute in sorted(set(fs_keys) | set(db_keys)):
        in_fs = (cert_fp, svc, minute) in fs_keys
        in_db = (cert_fp, svc, minute) in db_keys
        if in_fs and in_db:
            status = "joined"
        elif in_fs:
            status = "fs_only"
        else:
            status = "db_only"
        jk = fs_keys.get((cert_fp, svc, minute)) or db_keys[(cert_fp, svc, minute)]
        rows.append([cert_fp, svc, minute, jk, status])
    buf = io.StringIO()
    w = csv.writer(buf, delimiter="\t", lineterminator="\n")
    w.writerow(["cert_fp", "service_id", "access_minute", "join_key", "join_status"])
    w.writerows(rows)
    return buf.getvalue()


class CertValidator:
    def __init__(self, data_dir: Path, eff: dict[str, list[str]]):
        self.data_dir = data_dir
        self.authorities = _load_pems("authorities", data_dir)
        self.leaves = _load_pems("leaves", data_dir)
        self.trusted = load_trusted(data_dir)
        self.by_fp = set(eff["by_fingerprint"])
        self.by_name = set(eff["by_name"])
        self.T = datetime.strptime(
            (data_dir / "eval_time.txt").read_text().strip(), "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)

    def _paths(self, leaf: x509.Certificate) -> list[list[x509.Certificate]]:
        results: list[list[x509.Certificate]] = []

        def dfs(cur, chain, seen):
            if _self_signed(cur):
                results.append(list(chain))
                return
            for a in self.authorities:
                if a.subject.public_bytes() != cur.issuer.public_bytes():
                    continue
                if not _verify(cur, a):
                    continue
                if _cn(a) in seen:
                    continue
                dfs(a, chain + [a], seen | {_cn(a)})

        dfs(leaf, [leaf], {_cn(leaf)})
        return results

    def _tainted(self, chain):
        return sorted(_fp(m) for m in chain if _fp(m) in self.by_fp or _cn(m) in self.by_name)

    def _name_depth(self, chain):
        sans = _dns_sans(chain[0])
        best = None
        for i in range(1, len(chain)):
            permitted, excluded = _name_constraints(chain[i])
            bad = False
            if permitted and any(not any(_dns_match(e, s) for e in permitted) for s in sans):
                bad = True
            if excluded and any(_dns_match(e, s) for e in excluded for s in sans):
                bad = True
            if bad:
                best = i if best is None else min(best, i)
        return best

    def _status(self, chain):
        tainted = self._tainted(chain)
        if tainted:
            return "revoked", tainted, None
        vdepth = self._name_depth(chain)
        if vdepth is not None:
            return "name_constraint", [], vdepth
        if any(m.not_valid_after_utc < self.T for m in chain):
            return "expired", [], None
        if any(m.not_valid_before_utc > self.T for m in chain):
            return "not_yet_valid", [], None
        return "acceptable", [], None

    def verdict(self, leaf):
        all_paths = self._paths(leaf)
        anchored = [p for p in all_paths if _fp(p[-1]) in self.trusted]
        if not anchored:
            name_issuers = [a for a in self.authorities
                            if a.subject.public_bytes() == leaf.issuer.public_bytes()]
            reason = "bad_signature" if not all_paths and name_issuers else "no_path"
            return {
                "leaf": _cn(leaf), "decision": "rejected", "reason": reason,
                "paths_considered": 0, "constraint_depth": "", "tainted_members": "",
                "selected_path": _fp(leaf),
            }
        classified = [(self._status(p), p) for p in anchored]
        (status, tainted, vdepth), chain = min(
            classified,
            key=lambda cp: (RANK[cp[0][0]], len(cp[1]), tuple(_fp(m) for m in cp[1])))
        depth = str(vdepth) if status == "name_constraint" and vdepth is not None else ""
        return {
            "leaf": _cn(leaf),
            "decision": "accepted" if status == "acceptable" else "rejected",
            "reason": "valid" if status == "acceptable" else status,
            "paths_considered": len(anchored),
            "constraint_depth": depth,
            "tainted_members": ",".join(tainted),
            "selected_path": ",".join(_fp(m) for m in chain),
        }

    def tsv(self) -> str:
        results = [self.verdict(leaf) for leaf in self.leaves]
        results.sort(key=lambda r: r["leaf"])
        buf = io.StringIO()
        w = csv.writer(buf, delimiter="\t", lineterminator="\n")
        w.writerow(["leaf", "decision", "reason", "paths_considered",
                    "constraint_depth", "tainted_members", "selected_path"])
        for r in results:
            w.writerow([r["leaf"], r["decision"], r["reason"], r["paths_considered"],
                        r["constraint_depth"], r["tainted_members"], r["selected_path"]])
        return buf.getvalue()


def policy_ok(data_dir: Path) -> bool:
    min_d = max_d = None
    in_rem = False
    for line in (data_dir / "remediation.policy").read_text().splitlines():
        trim = line.strip()
        if trim == "[remediation]":
            in_rem = True
            continue
        if trim.startswith("[") and trim != "[remediation]":
            in_rem = False
        if in_rem and "=" in line:
            k, v = trim.split("=", 1)
            if k == "min_chain_depth":
                min_d = int(v)
            elif k == "max_chain_depth":
                max_d = int(v)
    return min_d is not None and max_d is not None and min_d <= max_d


def build_reference(data_dir: Path) -> dict[str, Any] | None:
    if not policy_ok(data_dir):
        return None
    post = load_post_distrust(data_dir)
    eff, warrant_summary, sql = build_warrant_patch(data_dir, post)
    access_tsv = build_access_evidence(data_dir)
    cert_tsv = CertValidator(data_dir, eff).tsv()
    digest = artifact_digest(sql, access_tsv, cert_tsv)
    return {
        "eff": eff,
        "warrant": warrant_summary,
        "sql": sql,
        "access_tsv": access_tsv,
        "cert_tsv": cert_tsv,
        "digest": digest,
        "policy_lines": (data_dir / "remediation.policy").read_text(),
    }


def run_binary(data_dir: Path, out_dir: Path) -> subprocess.CompletedProcess[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [str(BIN_PATH), "--incident", str(data_dir), "--write", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


def read_tsv(path: Path) -> list[dict[str, str]]:
    lines = path.read_text().splitlines()
    if not lines:
        return []
    headers = lines[0].split("\t")
    return [dict(zip(headers, row.split("\t"))) for row in lines[1:]]


def read_receipt(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def copy_dataset(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def db_distrust_fps(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    fps = [r[0] for r in conn.execute(
        "SELECT fingerprint FROM distrust_fingerprint ORDER BY fingerprint")]
    conn.close()
    return fps


@pytest.fixture(scope="module", autouse=True)
def _agent_run_once() -> None:
    assert BIN_PATH.is_file(), f"missing binary {BIN_PATH}"
    proc = run_binary(DATA_DIR, OUT_DIR)
    assert proc.returncode == 0, proc.stderr


@pytest.fixture(scope="module")
def expected() -> dict[str, Any]:
    ref = build_reference(DATA_DIR)
    assert ref is not None
    return ref


@pytest.fixture(scope="module")
def fp_by_cn() -> dict[str, str]:
    mapping = {}
    for c in _load_pems("authorities", DATA_DIR) + _load_pems("leaves", DATA_DIR):
        mapping[_cn(c)] = _fp(c)
    return mapping


def _cert_row(out_dir: Path, leaf: str) -> dict[str, str]:
    return next(r for r in read_tsv(out_dir / "certificate_decisions.tsv") if r["leaf"] == leaf)


# ------------------------------------------------------------------ structure
def test_binary_exists():
    """The trust_attest binary must be built under /app/trust-remediator/build."""
    assert BIN_PATH.is_file()
    assert os.access(BIN_PATH, os.X_OK)


def test_project_tree_under_trust_remediator():
    """Go project sources and Makefile live under /app/trust-remediator."""
    assert PROJECT_DIR.is_dir()
    assert (PROJECT_DIR / "go.mod").is_file()
    assert (PROJECT_DIR / "Makefile").is_file()
    assert list(PROJECT_DIR.rglob("*.go"))


def test_binary_mtime_not_older_than_sources():
    """Executable mtime must be at least as new as every project source file."""
    bin_mtime = BIN_PATH.stat().st_mtime
    for src in PROJECT_DIR.rglob("*"):
        if src.is_file() and src != BIN_PATH:
            suffix = src.suffix.lower()
            if suffix == ".go" or src.name in {"Makefile", "go.mod"}:
                assert src.stat().st_mtime <= bin_mtime + 1.0, f"{src} newer than binary"


def test_remediated_db_exists():
    """Successful run writes remediated_trust_store.db."""
    assert (OUT_DIR / "remediated_trust_store.db").is_file()


def test_remediation_sql_exists():
    """Successful run writes remediation.sql."""
    assert (OUT_DIR / "remediation.sql").is_file()


def test_remediated_policy_exists():
    """Successful run writes remediated.policy."""
    assert (OUT_DIR / "remediated.policy").is_file()


def test_access_evidence_tsv_exists():
    """Successful run writes access_evidence.tsv."""
    assert (OUT_DIR / "access_evidence.tsv").is_file()


def test_certificate_decisions_tsv_exists():
    """Successful run writes certificate_decisions.tsv."""
    assert (OUT_DIR / "certificate_decisions.tsv").is_file()


def test_audit_receipt_exists():
    """Successful run writes audit_receipt.txt."""
    assert (OUT_DIR / "audit_receipt.txt").is_file()


def test_no_json_output_artifacts():
    """Remediation emits domain-native artifacts, not JSON reports."""
    for p in OUT_DIR.iterdir():
        assert p.suffix != ".json"


def test_source_trust_store_unchanged(expected):
    """Incident trust_store.db must not be modified."""
    post = load_post_distrust(DATA_DIR)
    assert post["by_fingerprint"] == []


# ------------------------------------------------------------------ KMS patch
def test_post_migration_empty_fps(expected):
    """Post-migration store ships with zero fingerprint distrust rows."""
    assert load_post_distrust(DATA_DIR)["by_fingerprint"] == []


def test_remediation_sql_recovered_inter_b1(expected, fp_by_cn):
    """Accepted KMS restore adds inter-b1 fingerprint to remediation.sql."""
    inter_b1 = fp_by_cn["inter-b1"]
    sql = (OUT_DIR / "remediation.sql").read_text()
    assert inter_b1 in sql
    assert "INSERT OR IGNORE" in sql


def test_remediated_db_has_recovered_fp(expected, fp_by_cn):
    """Remediated DB contains recovered inter-b1 fingerprint distrust."""
    inter_b1 = fp_by_cn["inter-b1"]
    assert inter_b1 in db_distrust_fps(OUT_DIR / "remediated_trust_store.db")


def test_receipt_inert_warrants_counted(expected):
    """Warrants that fail a predicate are counted as inert in the receipt."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    assert int(rec["warrants_inert"]) == expected["warrant"]["warrants_inert"]


def test_receipt_honored_warrants_counted(expected):
    """Honoured warrants are counted in the receipt."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    assert int(rec["warrants_honored"]) == expected["warrant"]["warrants_honored"]


def test_receipt_counts_cover_every_warrant(expected):
    """Every warrant lands in exactly one of the two receipt buckets."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    conn = sqlite3.connect(DATA_DIR / "warrants" / "warrants.db")
    total = conn.execute("SELECT COUNT(*) FROM distrust_warrant").fetchone()[0]
    conn.close()
    assert int(rec["warrants_honored"]) + int(rec["warrants_inert"]) == total


def test_receipt_restored_fingerprints(expected, fp_by_cn):
    """Receipt lists inter-b1 among restored fingerprints."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    inter_b1 = fp_by_cn["inter-b1"]
    assert inter_b1 in rec["restored_fingerprints"].split(",")


def test_effective_name_preserved(expected):
    """Name-based distrust inter-a2 survives remediation."""
    conn = sqlite3.connect(OUT_DIR / "remediated_trust_store.db")
    names = [r[0] for r in conn.execute("SELECT common_name FROM distrust_name")]
    conn.close()
    assert "inter-a2" in names


def test_remediation_sql_matches_reference(expected):
    """remediation.sql matches independent patch construction."""
    assert (OUT_DIR / "remediation.sql").read_text() == expected["sql"]


# ------------------------------------------------------- warrant honouring predicates

LIVE_WINDOW = ("2026-01-01T00:00:00Z", "2026-06-01T00:00:00Z")
LAPSED_WINDOW = ("2025-01-01T00:00:00Z", "2025-06-01T00:00:00Z")


def reset_warrants(
    data: Path,
    warrants: list[tuple[Any, ...]],
    countersignatures: list[tuple[Any, ...]],
    countermands: list[tuple[Any, ...]] | None = None,
) -> None:
    """Replace the warrant fixtures in a copied dataset, keeping the signer roster."""
    conn = sqlite3.connect(data / "warrants" / "warrants.db")
    conn.execute("DELETE FROM distrust_warrant")
    conn.execute("DELETE FROM warrant_countersignature")
    conn.execute("DELETE FROM warrant_countermand")
    conn.executemany("INSERT INTO distrust_warrant VALUES (?,?,?,?,?,?,?)", warrants)
    conn.executemany(
        "INSERT INTO warrant_countersignature VALUES (?,?,?)", countersignatures
    )
    conn.executemany("INSERT INTO warrant_countermand VALUES (?,?)", countermands or [])
    conn.commit()
    conn.close()


def run_with_warrants(
    tmp_path: Path,
    warrants: list[tuple[Any, ...]],
    countersignatures: list[tuple[Any, ...]],
    countermands: list[tuple[Any, ...]] | None = None,
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    reset_warrants(data, warrants, countersignatures, countermands)
    out = tmp_path / "out"
    return out, run_binary(data, out)


def _two_custodians(wid: str) -> list[tuple[Any, ...]]:
    return [
        (wid, "cust-alpha", "2026-01-12T08:00:00Z"),
        (wid, "cust-bravo", "2026-01-12T08:05:00Z"),
    ]


def test_honourable_warrant_restores_the_fingerprint(tmp_path, fp_by_cn):
    """A warrant inside its window with quorum from a listed authority is honoured."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        _two_custodians("w-1"),
    )
    assert proc.returncode == 0, proc.stderr
    assert inter_b1 in db_distrust_fps(out / "remediated_trust_store.db")
    assert "'warrant_honored'" in (out / "remediation.sql").read_text()


def test_countermanded_warrant_is_inert(tmp_path, fp_by_cn):
    """A countermanded warrant adds no distrust even though every other check passes."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        _two_custodians("w-1"),
        [("w-1", "requestor_withdrew")],
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_single_countersignature_misses_quorum(tmp_path, fp_by_cn):
    """One custodian is short of a quorum of two."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        [("w-1", "cust-alpha", "2026-01-12T08:00:00Z")],
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_duplicate_countersignature_does_not_reach_quorum(tmp_path, fp_by_cn):
    """Two rows from one custodian are one endorsement, not two."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        [
            ("w-1", "cust-alpha", "2026-01-12T08:00:00Z"),
            ("w-1", "cust-alpha", "2026-01-12T09:30:00Z"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_observer_countersignature_does_not_count_toward_quorum(tmp_path, fp_by_cn):
    """Only signers rostered as custodians contribute endorsements."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        [
            ("w-1", "cust-alpha", "2026-01-12T08:00:00Z"),
            ("w-1", "obs-delta", "2026-01-12T08:02:00Z"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_unrostered_signatures_do_not_count_toward_quorum(tmp_path, fp_by_cn):
    """Signers absent from the roster contribute nothing."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        [
            ("w-1", "ghost-echo", "2026-01-12T08:00:00Z"),
            ("w-1", "ghost-foxtrot", "2026-01-12T08:02:00Z"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_lapsed_warrant_is_inert(tmp_path, fp_by_cn):
    """A warrant whose window closed before eval_time is inert."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LAPSED_WINDOW, "lapsed")],
        _two_custodians("w-1"),
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_warrant_from_distrusted_issuer_is_inert(tmp_path, fp_by_cn):
    """inter-a2 is distrusted post-migration, so it cannot authorise a warrant."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a2", *LIVE_WINDOW, "restore")],
        _two_custodians("w-1"),
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_warrant_from_unknown_issuer_is_inert(tmp_path, fp_by_cn):
    """An issuer naming no authority in the bundle cannot authorise a warrant."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-zz", *LIVE_WINDOW, "restore")],
        _two_custodians("w-1"),
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_warrant_row_order_does_not_change_the_patch(tmp_path, fp_by_cn):
    """Each warrant is judged on its own, so insertion order cannot matter."""
    inter_b1 = fp_by_cn["inter-b1"]
    inter_c1 = fp_by_cn["inter-c1"]
    forward = [
        ("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore"),
        ("w-2", "fingerprint", inter_c1, "root-a", *LIVE_WINDOW, "restore"),
    ]
    signatures = _two_custodians("w-1") + _two_custodians("w-2")

    out_a, proc_a = run_with_warrants(tmp_path / "a", forward, signatures)
    out_b, proc_b = run_with_warrants(
        tmp_path / "b", list(reversed(forward)), list(reversed(signatures))
    )
    assert proc_a.returncode == 0, proc_a.stderr
    assert proc_b.returncode == 0, proc_b.stderr
    assert (out_a / "remediation.sql").read_text() == (out_b / "remediation.sql").read_text()
    assert db_distrust_fps(out_a / "remediated_trust_store.db") == db_distrust_fps(
        out_b / "remediated_trust_store.db"
    )


def test_apply_remediation_sql_twice_idempotent(tmp_path, expected):
    """Applying remediation.sql twice yields identical distrust tables."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    out = tmp_path / "out"
    proc = run_binary(data, out)
    assert proc.returncode == 0
    db1 = tmp_path / "once.db"
    db2 = tmp_path / "twice.db"
    shutil.copy(data / "trust_store.db", db1)
    shutil.copy(data / "trust_store.db", db2)
    sql = (out / "remediation.sql").read_text()
    sql_file = tmp_path / "patch.sql"
    sql_file.write_text(sql)
    subprocess.run(["sqlite3", str(db1), f".read {sql_file}"], check=True)
    subprocess.run(["sqlite3", str(db2), f".read {sql_file}"], check=True)
    subprocess.run(["sqlite3", str(db2), f".read {sql_file}"], check=True)
    assert db_distrust_fps(db1) == db_distrust_fps(db2)


# ------------------------------------------------------------------ access evidence
def test_access_evidence_header():
    """access_evidence.tsv uses documented tab-separated header."""
    first = (OUT_DIR / "access_evidence.tsv").read_text().splitlines()[0]
    assert first == "cert_fp\tservice_id\taccess_minute\tjoin_key\tjoin_status"


def test_access_evidence_sorted(expected):
    """Access evidence rows are sorted by cert_fp, service_id, access_minute."""
    rows = read_tsv(OUT_DIR / "access_evidence.tsv")
    keys = [(r["cert_fp"], r["service_id"], r["access_minute"]) for r in rows]
    assert keys == sorted(keys)


def test_access_evidence_join_status_values(expected):
    """Every access row uses a documented join_status enum."""
    for r in read_tsv(OUT_DIR / "access_evidence.tsv"):
        assert r["join_status"] in {"joined", "fs_only", "db_only"}


def test_access_evidence_join_key_format(expected):
    """Join keys are 64-char lowercase hex digests."""
    for r in read_tsv(OUT_DIR / "access_evidence.tsv"):
        assert FP_RE.match(r["join_key"])


def test_access_evidence_has_joined(expected, fp_by_cn):
    """Production dataset includes at least one joined tuple."""
    leaf_fp = fp_by_cn["leaf-accept-a1"]
    joined = [r for r in read_tsv(OUT_DIR / "access_evidence.tsv")
              if r["join_status"] == "joined" and r["cert_fp"] == leaf_fp]
    assert joined


def test_access_evidence_has_fs_only(expected):
    """Production dataset includes fs_only classification."""
    assert any(r["join_status"] == "fs_only" for r in read_tsv(OUT_DIR / "access_evidence.tsv"))


def test_access_evidence_has_db_only(expected):
    """Production dataset includes db_only classification."""
    assert any(r["join_status"] == "db_only" for r in read_tsv(OUT_DIR / "access_evidence.tsv"))


def test_access_evidence_matches_reference(expected):
    """access_evidence.tsv matches independent join recomputation."""
    assert (OUT_DIR / "access_evidence.tsv").read_text() == expected["access_tsv"]


def test_metamorphic_permute_journal_order(tmp_path, expected):
    """Permuting journal line order does not change access evidence."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    lines = (data / "access" / "access.journal").read_text().splitlines()
    rev = "\n".join(reversed(lines)) + "\n"
    (data / "access" / "access.journal").write_text(rev)
    out = tmp_path / "out"
    proc = run_binary(data, out)
    assert proc.returncode == 0
    assert (out / "access_evidence.tsv").read_text() == expected["access_tsv"]


def test_metamorphic_remove_journal_row_becomes_db_only(tmp_path):
    """Removing a journal row reclassifies the tuple as db_only."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    kept = []
    for line in (data / "access" / "access.journal").read_text().splitlines():
        if "service=edge-gateway" in line:
            continue
        kept.append(line)
    (data / "access" / "access.journal").write_text("\n".join(kept) + "\n")
    out = tmp_path / "out"
    proc = run_binary(data, out)
    assert proc.returncode == 0
    edge = [r for r in read_tsv(out / "access_evidence.tsv") if r["service_id"] == "edge-gateway"]
    assert edge and edge[0]["join_status"] == "db_only"


def test_disjoint_journal_and_mirror_yield_both_one_sided_statuses(tmp_path, fp_by_cn):
    """A journal record and a mirror record that share nothing classify one-sided."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    fp_fs = fp_by_cn["leaf-revoked-byfp"]
    fp_db = fp_by_cn["leaf-expired"]
    (data / "access" / "access.journal").write_text(
        f"ACCESS cert_fp={fp_fs} service=legacy-ingest ts=2026-01-15T12:15:00Z "
        "record=fs-s1 bytes=1024\n"
    )
    conn = sqlite3.connect(data / "access" / "access_audit.db")
    conn.execute("DELETE FROM access_records")
    conn.execute(
        "INSERT INTO access_records VALUES (?,?,?,?,?,?)",
        ("db-s1", fp_db, "batch-runner", "2026-01-15T13:00:22Z",
         join_key(fp_db, "batch-runner", "2026-01-15T13:00:22Z"), 301),
    )
    conn.commit()
    conn.close()
    out = tmp_path / "out"
    proc = run_binary(data, out)
    assert proc.returncode == 0
    assert (out / "access_evidence.tsv").read_text() == build_access_evidence(data)
    assert {r["join_status"] for r in read_tsv(out / "access_evidence.tsv")} == {
        "fs_only",
        "db_only",
    }


# ------------------------------------------------------------------ policy
def test_unknown_policy_sections_preserved():
    """Unknown policy sections survive in remediated.policy."""
    text = (OUT_DIR / "remediated.policy").read_text()
    assert "[x_unknown_top]" in text
    assert "nested.deep.flag=preserve-me" in text
    assert "[extensions.legacy_cluster]" in text


def test_metamorphic_extra_unknown_policy_section(tmp_path, expected):
    """Injected unknown section is preserved through remediation."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    pol = (data / "remediation.policy").read_text()
    pol += "\n[injected.layer]\nmarker=metamorphic-xyz\n"
    (data / "remediation.policy").write_text(pol)
    out = tmp_path / "out"
    proc = run_binary(data, out)
    assert proc.returncode == 0
    assert "marker=metamorphic-xyz" in (out / "remediated.policy").read_text()
    assert (out / "remediation.sql").read_text() == expected["sql"]


def test_unknown_policy_sections_survive_remediation(tmp_path):
    """Sections and keys the tool knows nothing about are carried through verbatim."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    original = (data / "remediation.policy").read_text().rstrip("\n")
    added = [
        "[extensions.vendor_zeta]",
        "nested.deep.flag=preserve-me",
        "tier=7",
    ]
    (data / "remediation.policy").write_text(original + "\n\n" + "\n".join(added) + "\n")
    out = tmp_path / "out"
    proc = run_binary(data, out)
    assert proc.returncode == 0
    got = (out / "remediated.policy").read_text()
    for line in added:
        assert line in got


def test_contradictory_policy_rejects(tmp_path):
    """Contradictory min/max chain depth rejects without DB or SQL artifacts."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    pol_lines = (data / "remediation.policy").read_text().splitlines()
    out_lines = []
    for line in pol_lines:
        if line.startswith("min_chain_depth="):
            out_lines.append("min_chain_depth=9")
        elif line.startswith("max_chain_depth="):
            out_lines.append("max_chain_depth=2")
        else:
            out_lines.append(line)
    (data / "remediation.policy").write_text("\n".join(out_lines) + "\n")
    out = tmp_path / "out"
    proc = run_binary(data, out)
    assert proc.returncode != 0
    pol = (out / "remediated.policy").read_text()
    assert "status=rejected" in pol
    assert "reason=contradictory_known_fields" in pol
    assert not (out / "remediated_trust_store.db").exists()
    assert not (out / "remediation.sql").exists()
    assert not (out / "access_evidence.tsv").exists()


# ------------------------------------------------------------------ certificate validation
def test_cert_tsv_header():
    """certificate_decisions.tsv uses documented header."""
    first = (OUT_DIR / "certificate_decisions.tsv").read_text().splitlines()[0]
    assert first == "leaf\tdecision\treason\tpaths_considered\tconstraint_depth\ttainted_members\tselected_path"


def test_one_decision_per_leaf(expected):
    """Every leaf PEM yields exactly one certificate decision row."""
    rows = read_tsv(OUT_DIR / "certificate_decisions.tsv")
    assert len(rows) == len(_load_pems("leaves", DATA_DIR))


def test_decisions_sorted_by_leaf(expected):
    """Certificate decisions are sorted by leaf common name."""
    ids = [r["leaf"] for r in read_tsv(OUT_DIR / "certificate_decisions.tsv")]
    assert ids == sorted(ids)


def test_all_reasons_exercised(expected):
    """Every documented rejection/acceptance reason appears in production output."""
    reasons = {r["reason"] for r in read_tsv(OUT_DIR / "certificate_decisions.tsv")}
    assert REASONS <= reasons


def test_cert_tsv_matches_reference(expected):
    """certificate_decisions.tsv matches independent validation."""
    assert (OUT_DIR / "certificate_decisions.tsv").read_text() == expected["cert_tsv"]


def test_accept_simple_chain(fp_by_cn):
    """leaf-accept-a1 is accepted along the expected chain."""
    r = _cert_row(OUT_DIR, "leaf-accept-a1")
    assert (r["decision"], r["reason"]) == ("accepted", "valid")
    assert r["selected_path"] == f"{fp_by_cn['leaf-accept-a1']},{fp_by_cn['inter-a1']},{fp_by_cn['root-a']}"


def test_revoked_by_fingerprint_restored_by_warrant(fp_by_cn):
    """Recovered fingerprint distrust revokes leaf-revoked-byfp."""
    r = _cert_row(OUT_DIR, "leaf-revoked-byfp")
    assert r["reason"] == "revoked"
    assert fp_by_cn["inter-b1"] in r["tainted_members"].split(",")


def test_revoked_by_name(fp_by_cn):
    """Name distrust revokes leaf-revoked-byname."""
    r = _cert_row(OUT_DIR, "leaf-revoked-byname")
    assert r["reason"] == "revoked"
    assert fp_by_cn["inter-a2"] in r["tainted_members"].split(",")


def test_multipath_counts_both_roots():
    """Cross-signed leaf-multi anchors two paths."""
    r = _cert_row(OUT_DIR, "leaf-multi")
    assert int(r["paths_considered"]) == 2
    assert (r["decision"], r["reason"]) == ("accepted", "valid")


def test_crosspath_favorability_expired_over_revoked():
    """Cross-signed leaf with revoked and expired routes picks expired."""
    r = _cert_row(OUT_DIR, "leaf-crosspath")
    assert int(r["paths_considered"]) == 2
    assert r["reason"] == "expired"
    assert r["tainted_members"] == ""


def test_name_constraint_depth():
    """Name constraint violations report shallowest depth."""
    r = _cert_row(OUT_DIR, "leaf-namefail")
    assert r["reason"] == "name_constraint"
    assert r["constraint_depth"] == "1"


def test_expired_leaf():
    """Expired leaf is rejected with reason expired."""
    assert _cert_row(OUT_DIR, "leaf-expired")["reason"] == "expired"


def test_not_yet_valid_leaf():
    """Not-yet-valid leaf is rejected accordingly."""
    assert _cert_row(OUT_DIR, "leaf-notyet")["reason"] == "not_yet_valid"


def test_bad_signature_leaf(fp_by_cn):
    """Bad signature leaf is rejected without anchored paths."""
    r = _cert_row(OUT_DIR, "leaf-badsig")
    assert (r["decision"], r["reason"]) == ("rejected", "bad_signature")
    assert r["selected_path"] == fp_by_cn["leaf-badsig"]


def test_untrusted_root_no_path():
    """Leaf under untrusted root has no anchored path."""
    assert _cert_row(OUT_DIR, "leaf-untrusted")["reason"] == "no_path"


def test_metamorphic_crosspath_distrust_mutation(tmp_path, fp_by_cn):
    """An honourable warrant against the cross-path CA turns leaf-crosspath revoked."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    inter_exp = fp_by_cn["inter-exp"]
    conn = sqlite3.connect(data / "warrants" / "warrants.db")
    conn.execute(
        "INSERT INTO distrust_warrant VALUES (?,?,?,?,?,?,?)",
        ("wr-mutant", "fingerprint", inter_exp, "inter-a1",
         *LIVE_WINDOW, "crosspath_distrust"),
    )
    conn.executemany(
        "INSERT INTO warrant_countersignature VALUES (?,?,?)", _two_custodians("wr-mutant")
    )
    conn.commit()
    conn.close()
    out = tmp_path / "out"
    proc = run_binary(data, out)
    assert proc.returncode == 0
    assert _cert_row(out, "leaf-crosspath")["reason"] == "revoked"


def test_paths_considered_is_integer():
    """paths_considered column holds integer counts."""
    for r in read_tsv(OUT_DIR / "certificate_decisions.tsv"):
        pc = int(r["paths_considered"])
        assert isinstance(pc, int)


def test_revoked_iff_tainted_members():
    """Revoked reason iff tainted_members non-empty."""
    for r in read_tsv(OUT_DIR / "certificate_decisions.tsv"):
        if r["reason"] == "revoked":
            assert r["tainted_members"]
        else:
            assert r["tainted_members"] == ""


def test_selected_path_starts_with_leaf_fp(fp_by_cn):
    """Selected path always begins with the leaf fingerprint."""
    for r in read_tsv(OUT_DIR / "certificate_decisions.tsv"):
        assert r["selected_path"].split(",")[0] == fp_by_cn[r["leaf"]]


# ------------------------------------------------------------------ receipt digest
def test_receipt_artifact_digest(expected):
    """audit_receipt artifact_digest matches handbook concatenation rule."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    assert rec["artifact_digest"] == expected["digest"]


def test_receipt_digest_is_hex():
    """artifact_digest is 64-char lowercase hex."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    assert FP_RE.match(rec["artifact_digest"])


def test_remediated_policy_matches_input(expected):
    """Successful remediation preserves policy lines byte-for-byte."""
    assert (OUT_DIR / "remediated.policy").read_text() == expected["policy_lines"]

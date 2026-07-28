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
import itertools
import os
import re
import shutil
import sqlite3
import subprocess
from collections.abc import Iterator
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
MUTATIONS_DIR = Path(__file__).resolve().parent / "data" / "mutations"
HELD_OUT_JOURNAL = (
    Path(__file__).resolve().parent / "data" / "access" / "held_out.journal"
)

FP_RE = re.compile(r"^[0-9a-f]{64}$")
REASONS = {
    "valid",
    "bad_signature",
    "no_path",
    "revoked",
    "name_constraint",
    "expired",
    "not_yet_valid",
}
RANK = {
    "acceptable": 0,
    "not_yet_valid": 1,
    "expired": 2,
    "name_constraint": 3,
    "revoked": 4,
}


def access_minute(ts: str) -> str:
    return ts[:16]


def join_key(cert_fp: str, service_id: str, access_ts: str) -> str:
    raw = f"{cert_fp}:{service_id}:{access_minute(access_ts)}".encode()
    return hashlib.sha256(raw).hexdigest()


def artifact_digest(sql: str, access_tsv: str, signing_tsv: str, cert_tsv: str) -> str:
    h = hashlib.sha256()
    h.update(sql.encode())
    h.update(access_tsv.encode())
    h.update(signing_tsv.encode())
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
            child.signature,
            child.tbs_certificate_bytes,
            padding.PKCS1v15(),
            child.signature_hash_algorithm,
        )
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _self_signed(c: x509.Certificate) -> bool:
    return c.subject.public_bytes() == c.issuer.public_bytes() and _verify(c, c)


def _dns_sans(c: x509.Certificate) -> list[str]:
    try:
        ext = c.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        ).value
        return list(ext.get_values_for_type(x509.DNSName))
    except x509.ExtensionNotFound:
        return []


def _name_constraints(c: x509.Certificate) -> tuple[list[str], list[str]]:
    try:
        nc = c.extensions.get_extension_for_oid(ExtensionOID.NAME_CONSTRAINTS).value
    except x509.ExtensionNotFound:
        return [], []
    permitted = [
        g.value for g in (nc.permitted_subtrees or []) if isinstance(g, x509.DNSName)
    ]
    excluded = [
        g.value for g in (nc.excluded_subtrees or []) if isinstance(g, x509.DNSName)
    ]
    return permitted, excluded


def _dns_match(entry: str, dns: str) -> bool:
    return dns == entry or dns.endswith("." + entry)


def load_post_distrust(data_dir: Path) -> dict[str, list[str]]:
    conn = sqlite3.connect(data_dir / "trust_store.db")
    fps = [
        r[0]
        for r in conn.execute(
            "SELECT fingerprint FROM distrust_fingerprint ORDER BY fingerprint"
        )
    ]
    names = [
        r[0]
        for r in conn.execute(
            "SELECT common_name FROM distrust_name ORDER BY common_name"
        )
    ]
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


def subordinate_edges(data_dir: Path) -> dict[str, set[str]]:
    """issuer CN -> subject CNs it issued, skipping self-signed roots."""
    edges: dict[str, set[str]] = {}
    for pem in sorted((data_dir / "authorities").glob("*.pem")):
        cert = x509.load_pem_x509_certificate(pem.read_bytes())
        subject = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        issuer = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        if subject == issuer:
            continue
        edges.setdefault(issuer, set()).add(subject)
    return edges


def cascaded_authorities(data_dir: Path, seed_names: list[str]) -> set[str]:
    """Close the seed set over subordinate edges.

    The visited set is what keeps this terminating: cross-certified authorities
    point at each other, so the graph is not acyclic.
    """
    edges = subordinate_edges(data_dir)
    out = set(seed_names)
    frontier = list(out)
    while frontier:
        cur = frontier.pop()
        for child in edges.get(cur, ()):
            if child not in out:
                out.add(child)
                frontier.append(child)
    return out


def build_warrant_patch(
    data_dir: Path, base: dict[str, list[str]]
) -> tuple[dict[str, list[str]], dict[str, Any], str]:
    """Independently re-derive the honouring decision for every warrant.

    Each warrant is judged on its own against the post-migration store; nothing
    here depends on the order rows come back in.
    """
    conn = sqlite3.connect(data_dir / "warrants" / "warrants.db")
    warrants = conn.execute(
        "SELECT warrant_id, target_kind, target_value, issuer_cn, not_before, "
        "not_after FROM distrust_warrant ORDER BY warrant_id ASC"
    ).fetchall()
    terms = {
        r[0]: (r[1], r[2])
        for r in conn.execute(
            "SELECT signer_id, role_from, role_until FROM authorized_signer "
            "WHERE role = 'custodian'"
        )
    }
    # An endorsement counts only if the signer held the custodian role at the moment
    # it signed, which is signed_at and not eval_time.
    signers: dict[str, set[str]] = {}
    for wid, signer, signed_at in conn.execute(
        "SELECT warrant_id, signer_id, signed_at FROM warrant_countersignature"
    ):
        term = terms.get(signer)
        if term is None or not (term[0] <= signed_at <= term[1]):
            continue
        signers.setdefault(wid, set()).add(signer)
    countermanded = {
        r[0] for r in conn.execute("SELECT warrant_id FROM warrant_countermand")
    }
    conn.close()

    quorum = policy_warrant_quorum(data_dir)
    eval_time = (data_dir / "eval_time.txt").read_text().strip()
    authorities = authority_common_names(data_dir)
    cascaded = cascaded_authorities(data_dir, base["by_name"])

    fp_set = set(base["by_fingerprint"])
    name_set = set(base["by_name"])
    post_set = set(base["by_fingerprint"])
    honored = inert = 0
    stmts = ["-- trust store remediation patch"]

    for wid, kind, value, issuer, not_before, not_after in warrants:
        eligible = (
            kind in ("fingerprint", "common_name")
            and not_before <= eval_time <= not_after
            and len(signers.get(wid, set())) >= quorum
            and wid not in countermanded
            and issuer in authorities
            and issuer not in cascaded
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
    for journal in journal_paths(data_dir):
        for raw in journal.read_text().splitlines():
            line = raw.strip()
            if not line.startswith("ACCESS"):
                continue
            kv: dict[str, str] = {}
            for part in line.split()[1:]:
                if "=" in part:
                    k, v = part.split("=", 1)
                    kv[k] = v
            recs.append(
                {
                    "cert_fp": kv["cert_fp"],
                    "service_id": kv["service"],
                    "access_ts": kv["ts"],
                }
            )
    return recs


def journal_paths(data_dir: Path) -> list[Path]:
    paths = [data_dir / "access" / "access.journal"]
    held = data_dir / "access" / "held_out.journal"
    if held.is_file():
        paths.append(held)
    return paths


def parse_sign_events(data_dir: Path) -> list[dict[str, str]]:
    return parse_sign_events_from_paths(journal_paths(data_dir))


def parse_sign_events_from_paths(paths: list[Path]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for journal in paths:
        for raw in journal.read_text().splitlines():
            line = raw.strip()
            if not line.startswith("SIGN"):
                continue
            kv: dict[str, str] = {}
            for part in line.split()[1:]:
                if "=" in part:
                    k, v = part.split("=", 1)
                    kv[k] = v
            events.append(
                {
                    "cert_fp": kv["cert_fp"],
                    "signer_id": kv["signer"],
                    "event_ts": kv["ts"],
                }
            )
    return events


def parse_visible_sign_events(
    data_dir: Path, limit: int | None = None
) -> list[dict[str, str]]:
    """SIGN rows from access.journal only, in file order, optionally truncated."""
    events: list[dict[str, str]] = []
    for raw in (data_dir / "access" / "access.journal").read_text().splitlines():
        line = raw.strip()
        if not line.startswith("SIGN"):
            continue
        kv: dict[str, str] = {}
        for part in line.split()[1:]:
            if "=" in part:
                k, v = part.split("=", 1)
                kv[k] = v
        events.append(
            {
                "cert_fp": kv["cert_fp"],
                "signer_id": kv["signer"],
                "event_ts": kv["ts"],
            }
        )
        if limit is not None and len(events) >= limit:
            break
    return events


# First N visible SIGN rows omit spread out-of-window traps sg-oow-v-003/v-004.
VISIBLE_SUBSET_SIGN_LIMIT = 2100


def reconcile_key(cert_fp: str, signer_id: str, event_ts: str) -> str:
    raw = f"{cert_fp}:{signer_id}:{event_ts}".encode()
    return hashlib.sha256(raw).hexdigest()


def custodian_terms(data_dir: Path) -> dict[str, tuple[str, str]]:
    conn = sqlite3.connect(data_dir / "warrants" / "warrants.db")
    rows = conn.execute(
        "SELECT signer_id, role_from, role_until FROM authorized_signer "
        "WHERE role = 'custodian'"
    ).fetchall()
    conn.close()
    return {r[0]: (r[1], r[2]) for r in rows}


def signing_in_window(
    signer_id: str, event_ts: str, terms: dict[str, tuple[str, str]]
) -> bool:
    term = terms.get(signer_id)
    if term is None:
        return False
    return term[0] <= event_ts <= term[1]


def reconcile_sign_events(
    data_dir: Path, events: list[dict[str, str]]
) -> tuple[str, str, list[str]]:
    terms = custodian_terms(data_dir)
    rows: list[list[str]] = []
    keys: list[str] = []
    compromised_fps: set[str] = set()
    ordered = sorted(
        events,
        key=lambda e: (e["cert_fp"], e["signer_id"], e["event_ts"]),
    )
    for ev in ordered:
        rk = reconcile_key(ev["cert_fp"], ev["signer_id"], ev["event_ts"])
        in_win = signing_in_window(ev["signer_id"], ev["event_ts"], terms)
        status = "in_window" if in_win else "out_of_window"
        if status == "out_of_window":
            compromised_fps.add(ev["cert_fp"])
        keys.append(rk)
        rows.append([ev["cert_fp"], ev["signer_id"], ev["event_ts"], rk, status])
    buf = io.StringIO()
    w = csv.writer(buf, delimiter="\t", lineterminator="\n")
    header = ["cert_fp", "signer_id", "event_ts", "reconcile_key", "reconcile_status"]
    w.writerow(header)
    w.writerows(rows)
    tsv = buf.getvalue()
    if keys:
        digest = hashlib.sha256("".join(keys).encode()).hexdigest()
    else:
        digest = hashlib.sha256(b"").hexdigest()
    fp_to_cn = {_fp(c): _cn(c) for c in _load_pems("leaves", data_dir)}
    compromised = sorted(cn for fp, cn in fp_to_cn.items() if fp in compromised_fps)
    return tsv, digest, compromised


def build_signing_reconcile(data_dir: Path) -> tuple[str, str, list[str]]:
    return reconcile_sign_events(data_dir, parse_sign_events(data_dir))


def build_access_evidence(data_dir: Path) -> str:
    fs_recs = parse_journal(data_dir)
    conn = sqlite3.connect(data_dir / "access" / "access_audit.db")
    db_recs = [
        {"cert_fp": r[0], "service_id": r[1], "access_ts": r[2]}
        for r in conn.execute(
            "SELECT cert_fp, service_id, access_ts FROM access_records"
        )
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
    def __init__(
        self,
        data_dir: Path,
        eff: dict[str, list[str]],
        containment: list[str] | None = None,
    ):
        self.data_dir = data_dir
        self.authorities = _load_pems("authorities", data_dir)
        self.leaves = _load_pems("leaves", data_dir)
        self.trusted = load_trusted(data_dir)
        self.by_fp = set(eff["by_fingerprint"])
        self.by_name = set(eff["by_name"])
        # Honoured warrants never widen the cascade; the containment set does,
        # because it is chosen for what its members carry underneath them.
        self.cascaded = cascaded_authorities(
            data_dir,
            [*load_post_distrust(data_dir)["by_name"], *(containment or [])],
        )
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
                dfs(a, [*chain, a], seen | {_cn(a)})

        dfs(leaf, [leaf], {_cn(leaf)})
        return results

    def _tainted(self, chain):
        return sorted(
            _fp(m)
            for m in chain
            if _fp(m) in self.by_fp or _cn(m) in self.by_name or _cn(m) in self.cascaded
        )

    def _name_depth(self, chain):
        sans = _dns_sans(chain[0])
        best = None
        for i in range(1, len(chain)):
            permitted, excluded = _name_constraints(chain[i])
            bad = False
            if permitted and any(
                not any(_dns_match(e, s) for e in permitted) for s in sans
            ):
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
            name_issuers = [
                a
                for a in self.authorities
                if a.subject.public_bytes() == leaf.issuer.public_bytes()
            ]
            reason = "bad_signature" if not all_paths and name_issuers else "no_path"
            return {
                "leaf": _cn(leaf),
                "decision": "rejected",
                "reason": reason,
                "paths_considered": 0,
                "constraint_depth": "",
                "tainted_members": "",
                "selected_path": _fp(leaf),
            }
        classified = [(self._status(p), p) for p in anchored]
        (status, tainted, vdepth), chain = min(
            classified,
            key=lambda cp: (RANK[cp[0][0]], len(cp[1]), tuple(_fp(m) for m in cp[1])),
        )
        depth = (
            str(vdepth) if status == "name_constraint" and vdepth is not None else ""
        )
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
        w.writerow(
            [
                "leaf",
                "decision",
                "reason",
                "paths_considered",
                "constraint_depth",
                "tainted_members",
                "selected_path",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r["leaf"],
                    r["decision"],
                    r["reason"],
                    r["paths_considered"],
                    r["constraint_depth"],
                    r["tainted_members"],
                    r["selected_path"],
                ]
            )
        return buf.getvalue()


def load_exposure(data_dir: Path) -> list[tuple[str, str, str]]:
    """Rows of exposure.tsv as (incident, subject, disposition)."""
    rows = []
    lines = (data_dir / "exposure.tsv").read_text().rstrip("\n").split("\n")
    for line in lines[1:]:
        cols = line.split("\t")
        assert len(cols) == 3, f"bad exposure row: {line}"
        rows.append((cols[0], cols[1], cols[2]))
    return rows


def _sound_path(chain, eval_time) -> bool:
    """Whether a path would be accepted on its own merits, ignoring distrust."""
    sans = _dns_sans(chain[0])
    for i in range(1, len(chain)):
        permitted, excluded = _name_constraints(chain[i])
        if permitted and any(
            not any(_dns_match(e, s) for e in permitted) for s in sans
        ):
            return False
        if excluded and any(_dns_match(e, s) for e in excluded for s in sans):
            return False
    return all(
        m.not_valid_after_utc >= eval_time and m.not_valid_before_utc <= eval_time
        for m in chain
    )


def live_paths(data_dir: Path, eff: dict[str, list[str]]) -> dict[str, list[list[str]]]:
    """Per subject of exposure.tsv, the paths that still carry it.

    A path is live when it is anchored, sound on its own merits, and free of any
    member already distrusted once the honoured warrants are in force.
    """
    v = CertValidator(data_dir, eff)
    standing = set(eff["by_name"]) | cascaded_authorities(
        data_dir, load_post_distrust(data_dir)["by_name"]
    )
    wanted = {name for _, name, _ in load_exposure(data_dir)}
    out: dict[str, list[list[str]]] = {}
    for leaf in v.leaves:
        if _cn(leaf) not in wanted:
            continue
        keep = []
        for p in v._paths(leaf):
            if _fp(p[-1]) not in v.trusted or not _sound_path(p, v.T):
                continue
            members = [_cn(m) for m in p]
            if any(m in standing for m in members):
                continue
            keep.append(members)
        out[_cn(leaf)] = keep
    return out


def containment_constraints(
    data_dir: Path,
    eff: dict[str, list[str]],
    *,
    compromised_override: list[str] | None = None,
) -> tuple[list[str], list[str], dict[str, list[list[str]]]]:
    """Contain/preserve subjects and live paths for the full containment search."""
    live = live_paths(data_dir, eff)
    if compromised_override is None:
        _signing_tsv, _digest, compromised = build_signing_reconcile(data_dir)
    else:
        compromised = sorted(compromised_override)
    contain = sorted(
        {n for _, n, d in load_exposure(data_dir) if d == "contain"} | set(compromised)
    )
    preserve = [
        n
        for _, n, d in load_exposure(data_dir)
        if d == "preserve" and n not in compromised
    ]
    extra = [n for n in compromised if n not in live]
    if extra:
        v = CertValidator(data_dir, eff)
        standing = set(eff["by_name"]) | cascaded_authorities(
            data_dir, load_post_distrust(data_dir)["by_name"]
        )
        for leaf in v.leaves:
            name = _cn(leaf)
            if name not in extra:
                continue
            keep = []
            for p in v._paths(leaf):
                if _fp(p[-1]) not in v.trusted or not _sound_path(p, v.T):
                    continue
                members = [_cn(m) for m in p]
                if any(m in standing for m in members):
                    continue
                keep.append(members)
            live[name] = keep
    return contain, preserve, live


def containment_set(
    data_dir: Path,
    eff: dict[str, list[str]],
    *,
    compromised_override: list[str] | None = None,
) -> list[str]:
    """Smallest containment set, and first in name order among the smallest.

    Searched by brute force over authority common names so the answer does not
    depend on the order candidates happen to be considered.
    """
    contain, preserve, live = containment_constraints(
        data_dir, eff, compromised_override=compromised_override
    )
    edges = subordinate_edges(data_dir)
    candidates = sorted({_cn(a) for a in _load_pems("authorities", data_dir)})

    def feasible(chosen: tuple[str, ...]) -> bool:
        cut = cascaded_authorities(data_dir, list(chosen)) if chosen else set()
        for name in contain:
            if not all(any(m in cut for m in p) for p in live[name]):
                return False
        for name in preserve:
            if not any(all(m not in cut for m in p) for p in live[name]):
                return False
        return True

    assert edges, "subordinate graph is empty"
    for size in range(len(candidates) + 1):
        for combo in itertools.combinations(candidates, size):
            if feasible(combo):
                return list(combo)
    raise AssertionError("no containment set satisfies the incident")


def containment_sql(names: list[str]) -> str:
    return "".join(
        "INSERT OR IGNORE INTO distrust_name (common_name, source) "
        f"VALUES ('{n}', 'exposure_containment');\n"
        for n in sorted(names)
    )


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
    eff_warrants = eff
    contained = containment_set(data_dir, eff_warrants)
    sql = sql + containment_sql(contained)
    eff = {
        "by_fingerprint": eff_warrants["by_fingerprint"],
        "by_name": sorted({*eff_warrants["by_name"], *contained}),
    }
    access_tsv = build_access_evidence(data_dir)
    signing_tsv, journal_digest, compromised = build_signing_reconcile(data_dir)
    cert_tsv = CertValidator(data_dir, eff, contained).tsv()
    digest = artifact_digest(sql, access_tsv, signing_tsv, cert_tsv)
    return {
        "eff": eff,
        # The state the containment search runs against, before its own rows
        # are folded in. Using the merged set here would be circular.
        "eff_warrants": eff_warrants,
        "warrant": warrant_summary,
        "containment": contained,
        "compromised": compromised,
        "journal_digest": journal_digest,
        "sql": sql,
        "access_tsv": access_tsv,
        "signing_tsv": signing_tsv,
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
    return [dict(zip(headers, row.split("\t"), strict=False)) for row in lines[1:]]


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


def run_with_mutation(
    tmp_path: Path, mutation: str
) -> tuple[Path, Path, subprocess.CompletedProcess[str]]:
    """Copy the shipped incident bundle and swap exposure.tsv from tests/data."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    shutil.copy(MUTATIONS_DIR / mutation / "exposure.tsv", data / "exposure.tsv")
    stage_grading_journals(data)
    out = tmp_path / "out"
    return data, out, run_binary(data, out)


def mutation_data_dir(tmp_path: Path, mutation: str) -> Path:
    """Copy incident bundle with a held-out exposure.tsv, without running the binary."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    shutil.copy(MUTATIONS_DIR / mutation / "exposure.tsv", data / "exposure.tsv")
    stage_grading_journals(data)
    return data


def db_distrust_fps(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    fps = [
        r[0]
        for r in conn.execute(
            "SELECT fingerprint FROM distrust_fingerprint ORDER BY fingerprint"
        )
    ]
    conn.close()
    return fps


def stage_grading_journals(data_dir: Path) -> Path | None:
    """Copy held-out grading shard beside the incident journal when present."""
    dest = data_dir / "access" / "held_out.journal"
    if not HELD_OUT_JOURNAL.is_file():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(HELD_OUT_JOURNAL, dest)
    return dest


@pytest.fixture(scope="module", autouse=True)
def _agent_run_once() -> Iterator[None]:
    assert BIN_PATH.is_file(), f"missing binary {BIN_PATH}"
    staged = stage_grading_journals(DATA_DIR)
    proc = run_binary(DATA_DIR, OUT_DIR)
    assert proc.returncode == 0, proc.stderr
    yield
    # Staging writes the grading shard next to the incident journal. That is fine in a
    # throwaway container, but an authoring run on a workstation would leave it inside
    # the shipped tree, where a later package step would hand it straight to the agent.
    if staged is not None:
        staged.unlink(missing_ok=True)


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
    return next(
        r for r in read_tsv(out_dir / "certificate_decisions.tsv") if r["leaf"] == leaf
    )


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
                assert src.stat().st_mtime <= bin_mtime + 1.0, (
                    f"{src} newer than binary"
                )


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


def test_signing_reconcile_tsv_exists():
    """Successful run writes signing_reconcile.tsv."""
    assert (OUT_DIR / "signing_reconcile.tsv").is_file()


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


def reset_roster(data: Path, signers: list[tuple[Any, ...]]) -> None:
    """Replace the endorsement roster in a copied dataset."""
    conn = sqlite3.connect(data / "warrants" / "warrants.db")
    conn.execute("DELETE FROM authorized_signer")
    conn.executemany("INSERT INTO authorized_signer VALUES (?,?,?,?)", signers)
    conn.commit()
    conn.close()


WIDE_TERM = ("2025-01-01T00:00:00Z", "2027-01-01T00:00:00Z")


def run_with_roster(
    tmp_path: Path,
    warrants: list[tuple[Any, ...]],
    countersignatures: list[tuple[Any, ...]],
    signers: list[tuple[Any, ...]],
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    reset_warrants(data, warrants, countersignatures)
    reset_roster(data, signers)
    out = tmp_path / "out"
    return out, run_binary(data, out)


# ------------------------------------------------------------ custodian term windows


def test_endorsement_inside_signer_term_counts(tmp_path, fp_by_cn):
    """Two endorsements left inside their custodian terms reach quorum."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_roster(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        [
            ("w-1", "cust-alpha", "2026-01-12T08:00:00Z"),
            ("w-1", "cust-bravo", "2026-01-12T08:05:00Z"),
        ],
        [
            ("cust-alpha", "custodian", *WIDE_TERM),
            ("cust-bravo", "custodian", *WIDE_TERM),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert inter_b1 in db_distrust_fps(out / "remediated_trust_store.db")


def test_endorsement_before_signer_term_does_not_count(tmp_path, fp_by_cn):
    """A custodian appointed after it signed contributes nothing to quorum."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_roster(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        [
            ("w-1", "cust-alpha", "2026-01-12T08:00:00Z"),
            ("w-1", "cust-bravo", "2026-01-12T08:05:00Z"),
        ],
        [
            ("cust-alpha", "custodian", *WIDE_TERM),
            ("cust-bravo", "custodian", "2026-03-01T00:00:00Z", "2027-01-01T00:00:00Z"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_endorsement_after_signer_term_does_not_count(tmp_path, fp_by_cn):
    """A custodian whose term lapsed before it signed contributes nothing."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_roster(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        [
            ("w-1", "cust-alpha", "2026-01-12T08:00:00Z"),
            ("w-1", "cust-bravo", "2026-01-12T08:05:00Z"),
        ],
        [
            ("cust-alpha", "custodian", *WIDE_TERM),
            ("cust-bravo", "custodian", "2025-01-01T00:00:00Z", "2025-12-01T00:00:00Z"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_term_bounds_are_inclusive(tmp_path, fp_by_cn):
    """A signature landing exactly on a term bound still counts."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_roster(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        [
            ("w-1", "cust-alpha", "2026-01-12T08:00:00Z"),
            ("w-1", "cust-bravo", "2026-01-12T08:05:00Z"),
        ],
        [
            ("cust-alpha", "custodian", "2026-01-12T08:00:00Z", "2027-01-01T00:00:00Z"),
            ("cust-bravo", "custodian", "2025-01-01T00:00:00Z", "2026-01-12T08:05:00Z"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert inter_b1 in db_distrust_fps(out / "remediated_trust_store.db")


def test_term_is_tested_against_signed_at_not_eval_time(tmp_path, fp_by_cn):
    """Both signers are custodians at eval_time yet one signed outside its term.

    This pins the asymmetry between condition 2, which asks whether the warrant is
    live at eval_time, and condition 3, which asks whether each signer held the role
    when it signed. An implementation that tests the term against eval_time honours
    this warrant, because eval_time falls inside both terms.
    """
    eval_time = (DATA_DIR / "eval_time.txt").read_text().strip()
    late_from = "2026-01-13T00:00:00Z"
    assert late_from <= eval_time, "eval_time must sit inside the later term"
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_roster(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "restore")],
        [
            ("w-1", "cust-alpha", "2026-01-12T08:00:00Z"),
            ("w-1", "cust-bravo", "2026-01-12T08:05:00Z"),
        ],
        [
            ("cust-alpha", "custodian", *WIDE_TERM),
            ("cust-bravo", "custodian", late_from, "2027-01-01T00:00:00Z"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


# ----------------------------------------------------------- cascaded authority trust


def test_cascade_reaches_a_direct_subordinate(tmp_path, fp_by_cn):
    """inter-mesh is issued by the distrusted inter-a2, so it cannot authorise."""
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", fp_by_cn["inter-b1"], "inter-mesh", *LIVE_WINDOW, "x")],
        _two_custodians("w-1"),
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_cascade_reaches_a_grandchild_authority(tmp_path, fp_by_cn):
    """inter-ring-p sits two hops below inter-a2, so a one-level check misses it."""
    out, proc = run_with_warrants(
        tmp_path,
        [
            (
                "w-1",
                "fingerprint",
                fp_by_cn["inter-b1"],
                "inter-ring-p",
                *LIVE_WINDOW,
                "x",
            )
        ],
        _two_custodians("w-1"),
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_cascade_crosses_a_certification_cycle(tmp_path, fp_by_cn):
    """inter-ring-q is only reachable through the p/q cross-certification cycle."""
    out, proc = run_with_warrants(
        tmp_path,
        [
            (
                "w-1",
                "fingerprint",
                fp_by_cn["inter-b1"],
                "inter-ring-q",
                *LIVE_WINDOW,
                "x",
            )
        ],
        _two_custodians("w-1"),
    )
    assert proc.returncode == 0, proc.stderr
    assert db_distrust_fps(out / "remediated_trust_store.db") == []


def test_cascade_spares_a_clean_branch(tmp_path, fp_by_cn):
    """inter-a1 hangs off root-a with no distrusted ancestor, so it still authorises."""
    inter_b1 = fp_by_cn["inter-b1"]
    out, proc = run_with_warrants(
        tmp_path,
        [("w-1", "fingerprint", inter_b1, "inter-a1", *LIVE_WINDOW, "x")],
        _two_custodians("w-1"),
    )
    assert proc.returncode == 0, proc.stderr
    assert inter_b1 in db_distrust_fps(out / "remediated_trust_store.db")


def test_cascade_seed_ignores_names_added_by_warrants(tmp_path, fp_by_cn):
    """The seed is post-migration name distrust, so honouring cannot widen it.

    w-1 distrusts inter-a1 by name. If the cascade were recomputed from the patched
    store, inter-a1-sub would fall with it and w-2 would go inert. It does not.
    """
    target = fp_by_cn["inter-c1"]
    out, proc = run_with_warrants(
        tmp_path,
        [
            ("w-1", "common_name", "inter-a1", "root-a", *LIVE_WINDOW, "x"),
            ("w-2", "fingerprint", target, "inter-a1-sub", *LIVE_WINDOW, "x"),
        ],
        _two_custodians("w-1") + _two_custodians("w-2"),
    )
    assert proc.returncode == 0, proc.stderr
    assert target in db_distrust_fps(out / "remediated_trust_store.db")


def test_cross_signed_authority_tainted_through_its_distrusted_parent(fp_by_cn):
    """leaf-mesh-cascade has a clean route via inter-b1, but inter-mesh has fallen."""
    r = _cert_row(OUT_DIR, "leaf-mesh-cascade")
    assert r["reason"] == "revoked"
    assert fp_by_cn["inter-mesh"] in r["tainted_members"].split(",")


def test_leaf_below_certification_cycle_is_revoked(fp_by_cn):
    """leaf-ring-cycle only falls if the cascade walks past the p/q cycle."""
    r = _cert_row(OUT_DIR, "leaf-ring-cycle")
    assert r["reason"] == "revoked"
    tainted = r["tainted_members"].split(",")
    assert fp_by_cn["inter-ring-q"] in tainted


def test_cascaded_members_appear_in_tainted_members(fp_by_cn):
    """Every cascaded authority on the selected path is listed, not just the seed."""
    r = _cert_row(OUT_DIR, "leaf-ring-cycle")
    tainted = set(r["tainted_members"].split(","))
    selected = set(r["selected_path"].split(","))
    cascaded = cascaded_authorities(DATA_DIR, load_post_distrust(DATA_DIR)["by_name"])
    cn_by_fp = {v: k for k, v in fp_by_cn.items()}
    for member in selected:
        if cn_by_fp.get(member) in cascaded:
            assert member in tainted, f"{cn_by_fp[member]} is cascaded but not tainted"


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
    assert (out_a / "remediation.sql").read_text() == (
        out_b / "remediation.sql"
    ).read_text()
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
    joined = [
        r
        for r in read_tsv(OUT_DIR / "access_evidence.tsv")
        if r["join_status"] == "joined" and r["cert_fp"] == leaf_fp
    ]
    assert joined


def test_access_evidence_has_fs_only(expected):
    """Production dataset includes fs_only classification."""
    assert any(
        r["join_status"] == "fs_only" for r in read_tsv(OUT_DIR / "access_evidence.tsv")
    )


def test_access_evidence_has_db_only(expected):
    """Production dataset includes db_only classification."""
    assert any(
        r["join_status"] == "db_only" for r in read_tsv(OUT_DIR / "access_evidence.tsv")
    )


def test_access_evidence_matches_reference(expected):
    """access_evidence.tsv matches independent join recomputation."""
    assert (OUT_DIR / "access_evidence.tsv").read_text() == expected["access_tsv"]


def test_signing_reconcile_header(expected):
    """signing_reconcile.tsv uses documented tab-separated header."""
    first = (OUT_DIR / "signing_reconcile.tsv").read_text().splitlines()[0]
    assert first == "cert_fp\tsigner_id\tevent_ts\treconcile_key\treconcile_status"


def test_signing_reconcile_matches_reference(expected):
    """signing_reconcile.tsv matches independent custodian-window join."""
    assert (OUT_DIR / "signing_reconcile.tsv").read_text() == expected["signing_tsv"]


def test_signing_reconcile_status_values(expected):
    """Reconcile status is in_window or out_of_window only."""
    for r in read_tsv(OUT_DIR / "signing_reconcile.tsv"):
        assert r["reconcile_status"] in {"in_window", "out_of_window"}


def test_signing_reconcile_key_format(expected):
    """Reconcile keys are 64-char lowercase hex digests."""
    for r in read_tsv(OUT_DIR / "signing_reconcile.tsv"):
        assert FP_RE.match(r["reconcile_key"])


def test_signing_corpus_has_thousands_of_events(expected):
    """The reconciled signing corpus spans several thousand events."""
    rows = read_tsv(OUT_DIR / "signing_reconcile.tsv")
    assert len(rows) >= 6000


def test_receipt_journal_reconcile_digest(expected):
    """audit_receipt journal_reconcile_digest matches handbook fold rule."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    assert rec["journal_reconcile_digest"] == expected["journal_digest"]


def test_receipt_compromised_leaves(expected):
    """compromised_leaves lists journal-compromised leaf common names."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    reported = [n for n in rec["compromised_leaves"].split(",") if n]
    assert reported == expected["compromised"]


def test_signing_reconcile_has_out_of_window_in_visible_corpus():
    """Visible journal includes out_of_window rows, not only the held-out shard."""
    visible_paths = [DATA_DIR / "access" / "access.journal"]
    tsv, _digest, visible_comp = reconcile_sign_events(
        DATA_DIR, parse_sign_events_from_paths(visible_paths)
    )
    statuses = {line.split("\t")[4] for line in tsv.splitlines()[1:] if line}
    assert "out_of_window" in statuses
    assert visible_comp, "visible corpus alone must compromise at least one leaf"


def test_visible_out_of_window_compromises_leaf_revoked_byname():
    """Spread visible out-of-window signing compromises leaf-revoked-byname via join."""
    visible_paths = [DATA_DIR / "access" / "access.journal"]
    _tsv, _digest, visible_comp = reconcile_sign_events(
        DATA_DIR, parse_sign_events_from_paths(visible_paths)
    )
    assert "leaf-revoked-byname" in visible_comp


def test_out_of_window_rows_textually_match_in_window_shape():
    """Out-of-window SIGN rows share token shape and signer set with in-window rows."""
    rows = read_tsv(OUT_DIR / "signing_reconcile.tsv")
    oow = [r for r in rows if r["reconcile_status"] == "out_of_window"]
    inw = [r for r in rows if r["reconcile_status"] == "in_window"]
    assert oow and inw

    def shape(row: dict[str, str]) -> tuple[int, bool, int]:
        return (
            len(row["cert_fp"]),
            row["signer_id"].startswith("cust-"),
            len(row["event_ts"]),
        )

    assert {shape(r) for r in oow} <= {shape(r) for r in inw}
    assert {r["signer_id"] for r in oow} <= {r["signer_id"] for r in inw}


def test_compromised_leaf_from_held_out_shard(expected):
    """Held-out shard adds leaf-xc-one; visible corpus cannot reveal it alone."""
    visible_paths = [DATA_DIR / "access" / "access.journal"]
    _tsv, _digest, visible_comp = reconcile_sign_events(
        DATA_DIR, parse_sign_events_from_paths(visible_paths)
    )
    assert "leaf-xc-one" in expected["compromised"]
    assert "leaf-xc-one" not in visible_comp


def test_subset_visible_journal_coverage_loss_differs(tmp_path, expected):
    """Stopping early within the visible SIGN corpus changes the digest and list."""
    # The traps are no-new-cut, so containment stays the same; the only reliable
    # signal of an incomplete pass is the whole-corpus digest and the list of
    # journal-compromised leaves, which is the coverage-loss failure mode we want.
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    if (data / "access" / "held_out.journal").exists():
        (data / "access" / "held_out.journal").unlink()

    full_events = parse_visible_sign_events(data)
    subset_events = parse_visible_sign_events(data, limit=VISIBLE_SUBSET_SIGN_LIMIT)
    assert len(subset_events) < len(full_events)

    _full_tsv, full_digest, full_comp = reconcile_sign_events(data, full_events)
    _part_tsv, part_digest, part_comp = reconcile_sign_events(data, subset_events)

    assert part_digest != full_digest
    assert part_comp != full_comp
    # The first two traps are before the limit; the last two are after it.
    assert "leaf-mesh-cascade" in full_comp and "leaf-mesh-cascade" in part_comp
    assert "leaf-ring-cycle" in full_comp and "leaf-ring-cycle" in part_comp
    assert "leaf-revoked-byname" in full_comp
    assert "leaf-revoked-byname" not in part_comp
    assert "leaf-revoked-byname-deep" in full_comp
    assert "leaf-revoked-byname-deep" not in part_comp

    post = load_post_distrust(data)
    eff, _summary, _sql = build_warrant_patch(data, post)
    full_contain = containment_set(data, eff, compromised_override=full_comp)
    part_contain = containment_set(data, eff, compromised_override=part_comp)
    assert part_contain == full_contain, "visible traps are no-new-cut"
    assert part_contain == expected["containment"]


def test_metamorphic_permute_journal_order(tmp_path, expected):
    """Permuting journal line order does not change access evidence."""
    data = tmp_path / "data"
    copy_dataset(DATA_DIR, data)
    stage_grading_journals(data)
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
    edge = [
        r
        for r in read_tsv(out / "access_evidence.tsv")
        if r["service_id"] == "edge-gateway"
    ]
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
        (
            "db-s1",
            fp_db,
            "batch-runner",
            "2026-01-15T13:00:22Z",
            join_key(fp_db, "batch-runner", "2026-01-15T13:00:22Z"),
            301,
        ),
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
    (data / "remediation.policy").write_text(
        original + "\n\n" + "\n".join(added) + "\n"
    )
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


# certificate validation
def test_cert_tsv_header():
    """certificate_decisions.tsv uses documented header."""
    first = (OUT_DIR / "certificate_decisions.tsv").read_text().splitlines()[0]
    assert (
        first
        == "leaf\tdecision\treason\tpaths_considered\tconstraint_depth\t"
        "tainted_members\tselected_path"
    )


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
    assert reasons >= REASONS


def test_cert_tsv_matches_reference(expected):
    """certificate_decisions.tsv matches independent validation."""
    assert (OUT_DIR / "certificate_decisions.tsv").read_text() == expected["cert_tsv"]


def test_accept_simple_chain(fp_by_cn):
    """leaf-accept-a1 has only in-window signs and remains accepted."""
    r = _cert_row(OUT_DIR, "leaf-accept-a1")
    assert (r["decision"], r["reason"]) == ("accepted", "valid")
    assert r["selected_path"].split(",")[0] == fp_by_cn["leaf-accept-a1"]


def test_accept_direct_still_valid():
    """leaf-accept-direct signs only in window, so it survives the journal join."""
    visible_paths = [DATA_DIR / "access" / "access.journal"]
    _tsv, _digest, visible_comp = reconcile_sign_events(
        DATA_DIR, parse_sign_events_from_paths(visible_paths)
    )
    assert "leaf-accept-direct" not in visible_comp
    r = _cert_row(OUT_DIR, "leaf-accept-direct")
    assert r["decision"] == "accepted"


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
    """Cross-signed leaf-multi anchors two paths and stays acceptable."""
    r = _cert_row(OUT_DIR, "leaf-multi")
    assert int(r["paths_considered"]) == 2
    assert (r["decision"], r["reason"]) == ("accepted", "valid")


def test_crosspath_favorability_expired_over_revoked():
    """Cross-signed leaf-crosspath reports the more favourable expired reason."""
    r = _cert_row(OUT_DIR, "leaf-crosspath")
    assert int(r["paths_considered"]) == 2
    assert r["reason"] == "expired"


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
        (
            "wr-mutant",
            "fingerprint",
            inter_exp,
            "inter-a1",
            *LIVE_WINDOW,
            "crosspath_distrust",
        ),
    )
    conn.executemany(
        "INSERT INTO warrant_countersignature VALUES (?,?,?)",
        _two_custodians("wr-mutant"),
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


# ------------------------------------------------- exposure containment
def test_exposure_list_is_well_formed():
    """exposure.tsv carries one row per subject with a known disposition."""
    rows = load_exposure(DATA_DIR)
    assert rows, "incident list is empty"
    names = [n for _, n, _ in rows]
    assert len(names) == len(set(names))
    assert {d for _, _, d in rows} <= {"contain", "preserve"}


def test_exposure_names_real_leaves():
    """Every subject of the incident is a leaf in the bundle."""
    leaf_cns = {_cn(c) for c in _load_pems("leaves", DATA_DIR)}
    for _, name, _ in load_exposure(DATA_DIR):
        assert name in leaf_cns


def test_both_dispositions_present():
    """The incident exercises containment and preservation together."""
    dispositions = {d for _, _, d in load_exposure(DATA_DIR)}
    assert dispositions == {"contain", "preserve"}


def test_receipt_containment_matches_reference(expected):
    """containment_names equals the independently searched set."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    assert rec["containment_names"] == ",".join(expected["containment"])


def test_receipt_containment_size_matches_names(expected):
    """containment_size counts the names it reports."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    reported = [n for n in rec["containment_names"].split(",") if n]
    assert int(rec["containment_size"]) == len(reported)
    assert int(rec["containment_size"]) == len(expected["containment"])


def test_containment_names_are_authorities():
    """A containment set names authorities, never leaves."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    authority_cns = {_cn(a) for a in _load_pems("authorities", DATA_DIR)}
    leaf_cns = {_cn(c) for c in _load_pems("leaves", DATA_DIR)}
    for name in [n for n in rec["containment_names"].split(",") if n]:
        assert name in authority_cns
        assert name not in leaf_cns


def test_containment_names_sorted_and_distinct():
    """The reported set is in common-name order with no repeats."""
    rec = read_receipt(OUT_DIR / "audit_receipt.txt")
    reported = [n for n in rec["containment_names"].split(",") if n]
    assert reported == sorted(set(reported))


def test_containment_rows_present_in_sql(expected):
    """Each containment name lands in remediation.sql under its own source."""
    sql = (OUT_DIR / "remediation.sql").read_text()
    for name in expected["containment"]:
        assert (
            "INSERT OR IGNORE INTO distrust_name (common_name, source) "
            f"VALUES ('{name}', 'exposure_containment');" in sql
        )


def test_containment_rows_follow_warrant_rows(expected):
    """Containment statements come after the warrant statements."""
    sql = (OUT_DIR / "remediation.sql").read_text().splitlines()
    warrant_idx = [i for i, line in enumerate(sql) if "warrant_honored" in line]
    contain_idx = [i for i, line in enumerate(sql) if "exposure_containment" in line]
    assert contain_idx, "no containment statements written"
    if warrant_idx:
        assert min(contain_idx) > max(warrant_idx)
    assert contain_idx == sorted(contain_idx)
    assert len(contain_idx) == len(expected["containment"])


def test_containment_rows_land_in_remediated_store(expected):
    """The patched store carries the containment rows."""
    conn = sqlite3.connect(OUT_DIR / "remediated_trust_store.db")
    rows = {
        r[0]
        for r in conn.execute(
            "SELECT common_name FROM distrust_name "
            "WHERE source = 'exposure_containment'"
        )
    }
    conn.close()
    assert rows == set(expected["containment"])


def test_every_contained_subject_is_revoked():
    """A contained subject stops validating."""
    for _, name, disposition in load_exposure(DATA_DIR):
        if disposition != "contain":
            continue
        row = _cert_row(OUT_DIR, name)
        assert row["decision"] == "rejected"
        assert row["reason"] == "revoked"


def test_every_preserved_subject_is_accepted():
    """A preserved subject keeps validating."""
    for _, name, disposition in load_exposure(DATA_DIR):
        if disposition != "preserve":
            continue
        row = _cert_row(OUT_DIR, name)
        assert row["decision"] == "accepted"
        assert row["reason"] == "valid"


def test_contained_subject_had_more_than_one_live_path(expected):
    """At least one contained subject needed every one of several paths cut."""
    live = live_paths(DATA_DIR, expected["eff_warrants"])
    contained = [n for _, n, d in load_exposure(DATA_DIR) if d == "contain"]
    assert any(len(live[n]) > 1 for n in contained)


def test_containment_set_is_feasible(expected):
    """The reported set really does contain and preserve what it must."""
    constraints = containment_constraints(DATA_DIR, expected["eff_warrants"])
    contain, preserve, live = constraints
    cut = cascaded_authorities(DATA_DIR, expected["containment"])
    for name in contain:
        hit = [any(m in cut for m in p) for p in live[name]]
        assert all(hit), f"{name} keeps a live path"
    for name in preserve:
        hit = [any(m in cut for m in p) for p in live[name]]
        assert not all(hit), f"{name} lost every live path"


def test_no_smaller_containment_set_exists(expected):
    """No set smaller than the reported one satisfies the incident."""
    constraints = containment_constraints(DATA_DIR, expected["eff_warrants"])
    contain, preserve, live = constraints
    candidates = sorted({_cn(a) for a in _load_pems("authorities", DATA_DIR)})
    for size in range(len(expected["containment"])):
        for combo in itertools.combinations(candidates, size):
            cut = cascaded_authorities(DATA_DIR, list(combo)) if combo else set()
            ok = True
            for name in contain:
                if not all(any(m in cut for m in p) for p in live[name]):
                    ok = False
                    break
            if ok:
                for name in preserve:
                    if not any(all(m not in cut for m in p) for p in live[name]):
                        ok = False
                        break
            assert not ok, f"{combo} is smaller and still works"


def test_containment_is_first_among_the_smallest(expected):
    """Several sets tie on size, and the reported one sorts first."""
    constraints = containment_constraints(DATA_DIR, expected["eff_warrants"])
    contain, preserve, live = constraints
    candidates = sorted({_cn(a) for a in _load_pems("authorities", DATA_DIR)})
    size = len(expected["containment"])
    winners = []
    for combo in itertools.combinations(candidates, size):
        cut = cascaded_authorities(DATA_DIR, list(combo))
        ok = True
        for name in contain:
            if not all(any(m in cut for m in p) for p in live[name]):
                ok = False
                break
        if ok:
            for name in preserve:
                if not any(all(m not in cut for m in p) for p in live[name]):
                    ok = False
                    break
        if ok:
            winners.append(list(combo))
    assert len(winners) > 1, "no tie to break, so ordering is untested"
    assert min(winners) == expected["containment"]


def test_a_single_name_would_contain_but_breaks_preservation(expected):
    """The cheapest cut is refused because it takes the preserved subject with it."""
    _contain, preserve, live = containment_constraints(
        DATA_DIR, expected["eff_warrants"]
    )
    exposure_contain = [n for _, n, d in load_exposure(DATA_DIR) if d == "contain"]
    candidates = sorted({_cn(a) for a in _load_pems("authorities", DATA_DIR)})
    tempting = []
    for name in candidates:
        cut = cascaded_authorities(DATA_DIR, [name])
        covers = all(
            all(any(m in cut for m in p) for p in live[c]) for c in exposure_contain
        )
        if covers:
            tempting.append(name)
    assert tempting, "no single name contains everything, so the trap is absent"
    for name in tempting:
        cut = cascaded_authorities(DATA_DIR, [name])
        msg = f"{name} contains everything and preserves"
        preserves_live = any(
            all(any(m in cut for m in p) for p in live[k]) for k in preserve
        )
        assert preserves_live, msg


# ------------------------------------------------- containment ablations
def _ablation_answer(chooser) -> list[str]:
    post = load_post_distrust(DATA_DIR)
    eff, _summary, _sql = build_warrant_patch(DATA_DIR, post)
    return chooser(live_paths(DATA_DIR, eff), load_exposure(DATA_DIR))


def test_ablation_direct_issuers_give_the_wrong_set(expected):
    """Distrusting each contained subject's issuer is valid but not the answer."""

    def issuers(live, exposure):
        chosen = set()
        for _, name, disposition in exposure:
            if disposition != "contain":
                continue
            for p in live[name]:
                if len(p) > 1:
                    chosen.add(p[1])
        return sorted(chosen)

    naive = _ablation_answer(issuers)
    assert naive != expected["containment"]


def test_ablation_ignoring_the_cascade_gives_the_wrong_set(expected):
    """Treating distrust as stopping at the named authority changes the answer."""
    live = live_paths(DATA_DIR, expected["eff_warrants"])
    exposure = load_exposure(DATA_DIR)
    candidates = sorted({_cn(a) for a in _load_pems("authorities", DATA_DIR)})
    found = None
    for size in range(len(candidates) + 1):
        for combo in itertools.combinations(candidates, size):
            cut = set(combo)
            ok = True
            for _, name, disposition in exposure:
                hit = [any(m in cut for m in p) for p in live[name]]
                if (disposition == "contain" and not all(hit)) or (
                    disposition == "preserve" and all(hit)
                ):
                    ok = False
                if not ok:
                    break
            if ok:
                found = list(combo)
                break
        if found is not None:
            break
    assert found is not None
    assert found != expected["containment"]


def test_ablation_ignoring_preservation_gives_a_smaller_wrong_set(expected):
    """Dropping the preserve constraint admits a set the incident forbids."""
    live = live_paths(DATA_DIR, expected["eff_warrants"])
    contain = [n for _, n, d in load_exposure(DATA_DIR) if d == "contain"]
    candidates = sorted({_cn(a) for a in _load_pems("authorities", DATA_DIR)})
    found = None
    for size in range(len(candidates) + 1):
        for combo in itertools.combinations(candidates, size):
            cut = cascaded_authorities(DATA_DIR, list(combo)) if combo else set()
            if all(all(any(m in cut for m in p) for p in live[c]) for c in contain):
                found = list(combo)
                break
        if found is not None:
            break
    assert found is not None
    assert len(found) < len(expected["containment"])
    assert found != expected["containment"]


# ------------------------------------------------- held-out exposure mutations
@pytest.mark.parametrize("mutation", ["contain-only", "one-plus-keep"])
def test_mutation_exposure_containment_matches_reference(tmp_path, mutation):
    """Held-out exposure.tsv layouts must not be satisfied by hardcoded answers."""
    data, out, proc = run_with_mutation(tmp_path, mutation)
    assert proc.returncode == 0, proc.stderr
    ref = build_reference(data)
    assert ref is not None
    rec = read_receipt(out / "audit_receipt.txt")
    reported = [n for n in rec["containment_names"].split(",") if n]
    assert reported == ref["containment"]


def test_mutation_contain_only_differs_from_production(tmp_path, expected):
    """Contain-only layout optimizes to a different cut than EXP-7741."""
    data = mutation_data_dir(tmp_path, "contain-only")
    ref = build_reference(data)
    assert ref is not None
    assert ref["containment"] != expected["containment"]
    greedy = _ablation_answer(
        lambda live, exposure: sorted(
            {
                p[1]
                for _, name, disp in exposure
                if disp == "contain"
                for p in live[name]
                if len(p) > 1
            }
        )
    )
    assert greedy != ref["containment"]


def test_mutation_one_plus_keep_differs_from_production(tmp_path, expected):
    """Single contain plus preserve needs a smaller cut than EXP-7741."""
    data = mutation_data_dir(tmp_path, "one-plus-keep")
    ref = build_reference(data)
    assert ref is not None
    assert ref["containment"] != expected["containment"]
    assert len(ref["containment"]) < len(expected["containment"])

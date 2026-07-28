#!/usr/bin/env python3
"""Fixture generator for the trust-store DB remediation task.

Run on the host; excluded from the submission zip.

`python gen.py` regenerates everything including the PKI. RSA keys are random,
so that rewrites every fingerprint in the fixture set. `python gen.py --data-only`
loads the PEMs already on disk and rewrites just the SQLite stores, the journal
and the policy, which is what you want when changing warrant or access fixtures.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ENV = ROOT / "environment"
DATA = ENV / "data"
AUTH = DATA / "authorities"
LEAF = DATA / "leaves"
WARRANTS = DATA / "warrants"
ACCESS = DATA / "access"

WARRANT_QUORUM = 2

T = dt.datetime(2026, 1, 15, 12, 0, 0, tzinfo=dt.timezone.utc)
FAR_PAST = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
FAR_FUT = dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc)
EXPIRED_AFTER = dt.datetime(2025, 6, 1, tzinfo=dt.timezone.utc)
NOTYET_BEFORE = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc)

KEYS: dict[str, Any] = {}
CERTS: dict[str, x509.Certificate] = {}


def name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def newkey():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def build(
    subject_cn: str,
    issuer_cn: str,
    subject_key,
    issuer_key,
    *,
    ca: bool,
    nb=FAR_PAST,
    na=FAR_FUT,
    permitted=None,
    excluded=None,
    sans=None,
):
    b = (
        x509.CertificateBuilder()
        .subject_name(name(subject_cn))
        .issuer_name(name(issuer_cn))
        .public_key(subject_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(nb)
        .not_valid_after(na)
    )
    b = b.add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    if ca and (permitted or excluded):
        b = b.add_extension(
            x509.NameConstraints(
                permitted_subtrees=[x509.DNSName(d) for d in permitted] if permitted else None,
                excluded_subtrees=[x509.DNSName(d) for d in excluded] if excluded else None,
            ),
            critical=True,
        )
    if sans:
        b = b.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(s) for s in sans]), critical=False
        )
    return b.sign(issuer_key, hashes.SHA256())


def save(cert: x509.Certificate, folder: Path, basename: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{basename}.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    CERTS[basename] = cert


def fp(basename: str) -> str:
    c = CERTS[basename]
    return hashlib.sha256(c.public_bytes(serialization.Encoding.DER)).hexdigest()


def load_existing_pki() -> None:
    """Populate CERTS from the PEMs already on disk, leaving key material alone."""
    for folder in (AUTH, LEAF):
        for pem in sorted(folder.glob("*.pem")):
            CERTS[pem.stem] = x509.load_pem_x509_certificate(pem.read_bytes())


def access_minute(ts: str) -> str:
    return ts[:16]


def join_key(cert_fp: str, service_id: str, access_ts: str) -> str:
    raw = f"{cert_fp}:{service_id}:{access_minute(access_ts)}".encode()
    return hashlib.sha256(raw).hexdigest()


def journal_line(rec: dict[str, Any]) -> str:
    return (
        f"ACCESS cert_fp={rec['cert_fp']} service={rec['service_id']} "
        f"ts={rec['access_ts']} record={rec['record_id']} bytes={rec['bytes_read']}"
    )


def write_trust_store(
    path: Path,
    *,
    trusted: list[str],
    distrust_fp: list[str],
    distrust_name: list[str],
) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE trusted_roots (fingerprint TEXT PRIMARY KEY);
        CREATE TABLE distrust_fingerprint (fingerprint TEXT PRIMARY KEY, source TEXT NOT NULL);
        CREATE TABLE distrust_name (common_name TEXT PRIMARY KEY, source TEXT NOT NULL);
        CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    for f in trusted:
        conn.execute("INSERT INTO trusted_roots VALUES (?)", (f,))
    for f in distrust_fp:
        conn.execute(
            "INSERT INTO distrust_fingerprint VALUES (?, ?)", (f, "post_migration")
        )
    for n in distrust_name:
        conn.execute("INSERT INTO distrust_name VALUES (?, ?)", (n, "post_migration"))
    conn.execute(
        "INSERT INTO store_meta VALUES (?, ?)",
        ("migration_dedup_applied", "true"),
    )
    conn.execute(
        "INSERT INTO store_meta VALUES (?, ?)", ("rotation_id", "2026-01-10")
    )
    conn.commit()
    conn.close()


def write_warrant_db(path: Path, bundle: dict[str, list[tuple[Any, ...]]]) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE distrust_warrant (
            warrant_id    TEXT PRIMARY KEY,
            target_kind   TEXT NOT NULL,
            target_value  TEXT NOT NULL,
            issuer_cn     TEXT NOT NULL,
            not_before    TEXT NOT NULL,
            not_after     TEXT NOT NULL,
            justification TEXT NOT NULL
        );
        CREATE TABLE warrant_countersignature (
            warrant_id TEXT NOT NULL,
            signer_id  TEXT NOT NULL,
            signed_at  TEXT NOT NULL
        );
        CREATE TABLE warrant_countermand (
            warrant_id TEXT NOT NULL,
            reason     TEXT NOT NULL
        );
        CREATE TABLE authorized_signer (
            signer_id  TEXT PRIMARY KEY,
            role       TEXT NOT NULL,
            role_from  TEXT NOT NULL,
            role_until TEXT NOT NULL
        );
        """
    )
    conn.executemany("INSERT INTO distrust_warrant VALUES (?,?,?,?,?,?,?)", bundle["warrants"])
    conn.executemany(
        "INSERT INTO warrant_countersignature VALUES (?,?,?)", bundle["countersignatures"]
    )
    conn.executemany("INSERT INTO warrant_countermand VALUES (?,?)", bundle["countermands"])
    conn.executemany("INSERT INTO authorized_signer VALUES (?,?,?,?)", bundle["signers"])
    conn.commit()
    conn.close()


def write_access_db(path: Path, records: list[dict[str, Any]]) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE access_records (
            record_id TEXT PRIMARY KEY,
            cert_fp TEXT NOT NULL,
            service_id TEXT NOT NULL,
            access_ts TEXT NOT NULL,
            join_key TEXT NOT NULL,
            audit_seq INTEGER NOT NULL
        )"""
    )
    for rec in records:
        conn.execute(
            "INSERT INTO access_records VALUES (?,?,?,?,?,?)",
            (
                rec["record_id"],
                rec["cert_fp"],
                rec["service_id"],
                rec["access_ts"],
                rec["join_key"],
                rec["audit_seq"],
            ),
        )
    conn.commit()
    conn.close()


def base_policy_lines(**overrides: tuple[str, str]) -> list[str]:
    lines = [
        "# trust remediation policy — rotation 2026-01",
        "[remediation]",
        "version=1",
        "require_provenance=true",
        "min_chain_depth=1",
        "max_chain_depth=8",
        f"warrant_quorum={WARRANT_QUORUM}",
        "audit_tag=rotation-2026-01",
        "",
        "[extensions.vendor_acme]",
        "tier=3",
        "beta=true",
        "shadow_mode=false",
        "",
        "[extensions.legacy_cluster]",
        "note=keep-through-rotation",
        "nested.seq=1,2,3",
        "",
        "[x_unknown_top]",
        "nested.deep.flag=preserve-me",
        "",
        "[service_profiles.edge-gateway]",
        "tier=edge",
        "region=us-east-1",
        "",
        "[service_profiles.mesh-proxy]",
        "tier=mesh",
        "region=us-west-2",
        "",
        "[service_profiles.legacy-ingest]",
        "tier=batch",
        "region=eu-central-1",
        "",
        "[service_profiles.batch-runner]",
        "tier=batch",
        "region=ap-south-1",
    ]
    if overrides:
        out = []
        for line in lines:
            if "=" in line and not line.startswith("#") and not line.startswith("["):
                key = line.split("=", 1)[0]
                if key in overrides:
                    out.append(f"{key}={overrides[key]}")
                    continue
            out.append(line)
        return out
    return lines


def write_policy(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n")


def generate_pki() -> None:
    for d in (AUTH, LEAF):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    def root(cn: str, basename: str):
        k = newkey()
        KEYS[cn] = k
        c = build(cn, cn, k, k, ca=True)
        save(c, AUTH, basename)

    def inter(
        cn: str,
        issuer_cn: str,
        basename: str,
        *,
        permitted=None,
        excluded=None,
        nb=FAR_PAST,
        na=FAR_FUT,
        subject_key_of=None,
    ):
        if subject_key_of and subject_key_of in KEYS:
            k = KEYS[subject_key_of]
        else:
            k = newkey()
            KEYS[cn] = k
        c = build(
            cn,
            issuer_cn,
            k,
            KEYS[issuer_cn],
            ca=True,
            permitted=permitted,
            excluded=excluded,
            nb=nb,
            na=na,
        )
        save(c, AUTH, basename)

    def leaf(
        cn: str,
        issuer_cn: str,
        basename: str,
        *,
        sans,
        nb=FAR_PAST,
        na=FAR_FUT,
        sign_bad=False,
    ):
        k = newkey()
        KEYS[cn] = k
        issuer_key = newkey() if sign_bad else KEYS[issuer_cn]
        c = build(cn, issuer_cn, k, issuer_key, ca=False, nb=nb, na=na, sans=sans)
        save(c, LEAF, basename)

    root("root-a", "root-a")
    root("root-b", "root-b")
    root("root-c", "root-c")
    inter("inter-a1", "root-a", "inter-a1", permitted=["a1.example"])
    inter("inter-a1-sub", "inter-a1", "inter-a1-sub", permitted=["sub.a1.example"])
    inter("inter-a2", "root-a", "inter-a2")
    inter("inter-a2-sub", "inter-a2", "inter-a2-sub")
    inter("inter-b1", "root-b", "inter-b1")
    inter("inter-exc", "root-a", "inter-exc", excluded=["secret.example"])
    inter("inter-exp", "root-a", "inter-exp", na=EXPIRED_AFTER)
    inter("inter-c1", "root-c", "inter-c1")
    inter("inter-shared", "root-a", "inter-shared-a")
    inter("inter-shared", "root-b", "inter-shared-b", subject_key_of="inter-shared")
    inter("inter-fav", "inter-b1", "inter-fav-b1")
    inter("inter-fav", "inter-exp", "inter-fav-exp", subject_key_of="inter-fav")
    # inter-mesh is cross-signed by a name-distrusted parent and a clean one, so the
    # clean path only looks clean until subordinate distrust is carried down.
    inter("inter-mesh", "inter-a2", "inter-mesh-a2")
    inter("inter-mesh", "inter-b1", "inter-mesh-b1", subject_key_of="inter-mesh")
    # inter-ring-p and inter-ring-q cross-certify each other, so the subordinate graph
    # below inter-mesh contains a cycle.
    inter("inter-ring-p", "inter-mesh", "inter-ring-p")
    inter("inter-ring-q", "inter-ring-p", "inter-ring-q")
    inter("inter-ring-p", "inter-ring-q", "inter-ring-p-alt", subject_key_of="inter-ring-p")
    # Exposure subtree. xc-delta and xc-epsil are each cross-signed by two of the
    # three second-tier authorities, so their cascade sets overlap without nesting.
    # xc-beta covers both exposed leaves on its own but also carries the leaf the
    # incident requires be preserved, so the cheapest containment is not available.
    inter("xc-alpha", "root-a", "xc-alpha")
    inter("xc-beta", "root-a", "xc-beta")
    inter("xc-gamma", "root-a", "xc-gamma")
    inter("xc-delta", "xc-alpha", "xc-delta-alpha")
    inter("xc-delta", "xc-beta", "xc-delta-beta", subject_key_of="xc-delta")
    inter("xc-epsil", "xc-beta", "xc-epsil-beta")
    inter("xc-epsil", "xc-gamma", "xc-epsil-gamma", subject_key_of="xc-epsil")
    leaf("leaf-accept-a1", "inter-a1", "leaf-accept-a1", sans=["host.a1.example"])
    leaf("leaf-accept-deep", "inter-a1-sub", "leaf-accept-deep", sans=["x.sub.a1.example"])
    leaf("leaf-accept-direct", "root-a", "leaf-accept-direct", sans=["direct.example"])
    leaf("leaf-multi", "inter-shared", "leaf-multi", sans=["m.example"])
    leaf("leaf-namefail", "inter-a1", "leaf-namefail", sans=["host.evil.example"])
    leaf("leaf-namefail-deep", "inter-a1-sub", "leaf-namefail-deep", sans=["host.a1.example"])
    leaf("leaf-excluded", "inter-exc", "leaf-excluded", sans=["x.secret.example"])
    leaf("leaf-revoked-byname", "inter-a2", "leaf-revoked-byname", sans=["r1.example"])
    leaf("leaf-revoked-byname-deep", "inter-a2-sub", "leaf-revoked-byname-deep", sans=["r2.example"])
    leaf("leaf-revoked-byfp", "inter-b1", "leaf-revoked-byfp", sans=["r3.example"])
    leaf(
        "leaf-revoked-and-expired",
        "inter-b1",
        "leaf-revoked-and-expired",
        sans=["r4.example"],
        na=EXPIRED_AFTER,
    )
    leaf("leaf-expired", "inter-a1", "leaf-expired", sans=["host.a1.example"], na=EXPIRED_AFTER)
    leaf("leaf-notyet", "inter-a1", "leaf-notyet", sans=["host.a1.example"], nb=NOTYET_BEFORE)
    leaf("leaf-badsig", "root-a", "leaf-badsig", sans=["b.example"], sign_bad=True)
    leaf("leaf-untrusted", "inter-c1", "leaf-untrusted", sans=["u.example"])
    leaf("leaf-crosspath", "inter-fav", "leaf-crosspath", sans=["f.example"])
    leaf("leaf-mesh-cascade", "inter-mesh", "leaf-mesh-cascade", sans=["mesh.example"])
    leaf("leaf-ring-cycle", "inter-ring-q", "leaf-ring-cycle", sans=["ring.example"])
    leaf("leaf-xc-one", "xc-delta", "leaf-xc-one", sans=["one.example"])
    leaf("leaf-xc-two", "xc-epsil", "leaf-xc-two", sans=["two.example"])
    leaf("leaf-xc-keep", "xc-beta", "leaf-xc-keep", sans=["keep.example"])


def build_warrants() -> dict[str, list[tuple[Any, ...]]]:
    """Twelve warrants covering both polarities of every honouring predicate.

    Three are honourable. Each of the other nine fails exactly one predicate, so a
    solver that drops any single check over-applies distrust in a visible way, and
    an ablation can attribute the damage to the check it skipped.
    """
    live = ("2026-01-01T00:00:00Z", "2026-06-01T00:00:00Z")
    lapsed = ("2025-01-01T00:00:00Z", "2025-06-01T00:00:00Z")

    warrants = [
        # honourable: restores the fingerprint the migration dropped
        ("wr-4501", "fingerprint", fp("inter-b1"), "inter-a1", *live, "migration_dedup_loss"),
        # honourable: reconfirms a name already distrusted post-migration
        ("wr-4502", "common_name", "inter-a2", "root-a", *live, "confirm_name_distrust"),
        # inert: no countersignature from an authorised custodian
        ("wr-4503", "fingerprint", "0" * 64, "inter-a1", *live, "stale_ticket"),
        # inert: validity window closed before eval_time
        ("wr-4504", "fingerprint", fp("inter-c1"), "inter-a1", *lapsed, "lapsed_window"),
        # inert: issuing authority is itself distrusted by name
        ("wr-4505", "common_name", "inter-shared-a", "inter-a2", *live, "issuer_under_distrust"),
        # inert: countermanded after issue
        ("wr-4506", "fingerprint", fp("inter-exp"), "root-b", *live, "withdrawn_request"),
        # inert: quorum reached only by counting one custodian twice
        ("wr-4507", "fingerprint", fp("inter-exc"), "root-a", *live, "duplicate_countersign"),
        # inert: issuer names no authority in the incident bundle
        ("wr-4508", "fingerprint", fp("inter-fav-b1"), "inter-zz", *live, "unknown_issuer"),
        # honourable: both endorsements fall inside their signer's custodian term
        ("wr-4509", "fingerprint", fp("inter-a2-sub"), "root-a", *live, "post_rotation_review"),
        # inert: issuer sits two hops below a name-distrusted authority
        ("wr-4510", "fingerprint", fp("inter-a1"), "inter-ring-p", *live, "issuer_under_cascade"),
        # inert: quorum only if an endorsement predating its signer's term is counted
        ("wr-4511", "fingerprint", fp("inter-exp"), "root-a", *live, "endorsed_before_term"),
        # inert: quorum only if an endorsement after its signer's term is counted
        ("wr-4512", "fingerprint", fp("inter-shared-a"), "root-b", *live, "endorsed_after_term"),
    ]

    countersignatures = [
        ("wr-4501", "cust-alpha", "2026-01-12T08:00:00Z"),
        ("wr-4501", "cust-bravo", "2026-01-12T08:05:00Z"),
        ("wr-4502", "cust-alpha", "2026-01-12T09:00:00Z"),
        ("wr-4502", "cust-charlie", "2026-01-12T09:07:00Z"),
        # unknown signer plus an observer: neither counts toward quorum
        ("wr-4503", "ghost-echo", "2026-01-12T10:00:00Z"),
        ("wr-4503", "obs-delta", "2026-01-12T10:01:00Z"),
        ("wr-4504", "cust-alpha", "2025-02-01T10:00:00Z"),
        ("wr-4504", "cust-bravo", "2025-02-01T10:02:00Z"),
        ("wr-4505", "cust-bravo", "2026-01-12T11:00:00Z"),
        ("wr-4505", "cust-charlie", "2026-01-12T11:03:00Z"),
        ("wr-4506", "cust-alpha", "2026-01-12T12:00:00Z"),
        ("wr-4506", "cust-charlie", "2026-01-12T12:04:00Z"),
        # same custodian twice: one distinct custodian, not two
        ("wr-4507", "cust-alpha", "2026-01-12T13:00:00Z"),
        ("wr-4507", "cust-alpha", "2026-01-12T13:30:00Z"),
        ("wr-4508", "cust-bravo", "2026-01-12T14:00:00Z"),
        ("wr-4508", "cust-charlie", "2026-01-12T14:02:00Z"),
        # both inside their terms
        ("wr-4509", "cust-bravo", "2026-01-12T16:00:00Z"),
        ("wr-4509", "cust-charlie", "2026-01-12T16:02:00Z"),
        # both inside their terms, so only the issuer cascade can make this inert
        ("wr-4510", "cust-alpha", "2026-01-12T17:00:00Z"),
        ("wr-4510", "cust-bravo", "2026-01-12T17:04:00Z"),
        # cust-echo's custodian term starts after this signature
        ("wr-4511", "cust-alpha", "2026-01-12T18:00:00Z"),
        ("wr-4511", "cust-echo", "2026-01-12T18:03:00Z"),
        # cust-foxtrot's custodian term ended before this signature
        ("wr-4512", "cust-charlie", "2026-01-12T19:00:00Z"),
        ("wr-4512", "cust-foxtrot", "2026-01-12T19:05:00Z"),
    ]

    countermands = [("wr-4506", "requestor_withdrew")]

    wide = ("2025-01-01T00:00:00Z", "2027-01-01T00:00:00Z")
    signers = [
        ("cust-alpha", "custodian", *wide),
        ("cust-bravo", "custodian", *wide),
        ("cust-charlie", "custodian", *wide),
        ("obs-delta", "observer", *wide),
        # appointed after the signature it left on wr-4511
        ("cust-echo", "custodian", "2026-02-01T00:00:00Z", "2027-01-01T00:00:00Z"),
        # term lapsed before the signature it left on wr-4512
        ("cust-foxtrot", "custodian", "2025-01-01T00:00:00Z", "2025-12-01T00:00:00Z"),
    ]

    return {
        "warrants": warrants,
        "countersignatures": countersignatures,
        "countermands": countermands,
        "signers": signers,
    }


def build_access_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    samples = [
        ("leaf-accept-a1", "edge-gateway", "2026-01-15T10:30:45Z", "joined"),
        ("leaf-multi", "mesh-proxy", "2026-01-15T11:00:12Z", "joined"),
        ("leaf-crosspath", "mesh-proxy", "2026-01-15T11:00:55Z", "joined"),
        ("leaf-revoked-byfp", "legacy-ingest", "2026-01-15T12:15:00Z", "fs_only"),
        ("leaf-expired", "batch-runner", "2026-01-15T13:00:00Z", "db_only"),
        ("inter-b1", "legacy-ingest", "2026-01-15T12:14:30Z", "joined"),
    ]
    fs_lines: list[dict[str, Any]] = []
    db_records: list[dict[str, Any]] = []
    audit_seq = 100
    for idx, (cert_base, svc, ts, kind) in enumerate(samples, start=1):
        cert_fp_val = fp(cert_base)
        if kind in ("joined", "fs_only"):
            fs_lines.append(
                {
                    "record_id": f"fs-{idx:03d}",
                    "cert_fp": cert_fp_val,
                    "service_id": svc,
                    "access_ts": ts,
                    "bytes_read": 4096 + idx,
                }
            )
        if kind in ("joined", "db_only"):
            db_ts = ts if kind == "joined" else "2026-01-15T13:00:22Z"
            db_records.append(
                {
                    "record_id": f"db-{idx:03d}",
                    "cert_fp": cert_fp_val,
                    "service_id": svc,
                    "access_ts": db_ts,
                    "join_key": join_key(cert_fp_val, svc, db_ts),
                    "audit_seq": audit_seq,
                }
            )
            audit_seq += 1
    return fs_lines, db_records


def write_dataset(
    dest: Path,
    *,
    warrant_bundle: dict[str, list[tuple[Any, ...]]] | None = None,
    policy_lines: list[str] | None = None,
    include_leaves: bool = True,
    include_authorities: bool = True,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if include_authorities:
        auth_d = dest / "authorities"
        auth_d.mkdir(exist_ok=True)
        for pem in AUTH.glob("*.pem"):
            shutil.copy(pem, auth_d / pem.name)
    if include_leaves:
        leaf_d = dest / "leaves"
        leaf_d.mkdir(exist_ok=True)
        for pem in LEAF.glob("*.pem"):
            shutil.copy(pem, leaf_d / pem.name)
    write_data_artifacts(dest, warrant_bundle=warrant_bundle, policy_lines=policy_lines)


def write_data_artifacts(
    dest: Path,
    *,
    warrant_bundle: dict[str, list[tuple[Any, ...]]] | None = None,
    policy_lines: list[str] | None = None,
) -> None:
    write_trust_store(
        dest / "trust_store.db",
        trusted=sorted([fp("root-a"), fp("root-b")]),
        distrust_fp=[],
        distrust_name=["inter-a2"],
    )

    bundle = warrant_bundle if warrant_bundle is not None else build_warrants()
    warrant_d = dest / "warrants"
    warrant_d.mkdir(parents=True, exist_ok=True)
    write_warrant_db(warrant_d / "warrants.db", bundle)

    fs_lines, db_records = build_access_records()
    access_d = dest / "access"
    access_d.mkdir(parents=True, exist_ok=True)
    with (access_d / "access.journal").open("w") as fh:
        for rec in fs_lines:
            fh.write(journal_line(rec) + "\n")
    write_access_db(access_d / "access_audit.db", db_records)

    write_policy(dest / "remediation.policy", policy_lines or base_policy_lines())
    (dest / "eval_time.txt").write_text(T.strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")
    write_exposure(dest / "exposure.tsv")


def write_exposure(path: Path) -> None:
    rows = [
        ("EXP-7741", "leaf-xc-one", "contain"),
        ("EXP-7741", "leaf-xc-two", "contain"),
        ("EXP-7741", "leaf-xc-keep", "preserve"),
    ]
    with path.open("w") as fh:
        fh.write("incident\tsubject\tdisposition\n")
        for row in rows:
            fh.write("\t".join(row) + "\n")


def main() -> None:
    data_only = "--data-only" in sys.argv
    if data_only:
        load_existing_pki()
    else:
        generate_pki()
    write_data_artifacts(DATA)

    bundle = build_warrants()
    print(
        "authorities:", len(list(AUTH.glob("*.pem"))),
        "| leaves:", len(list(LEAF.glob("*.pem"))),
        "| warrants:", len(bundle["warrants"]),
        "| countersignatures:", len(bundle["countersignatures"]),
        "| pki:", "reused" if data_only else "regenerated",
    )


if __name__ == "__main__":
    main()

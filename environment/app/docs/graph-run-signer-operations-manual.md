# GraphRun pipeline operations manual

This manual records policy lineage, approval rosters, active-key selection,
callback schema governance, and incident response for the GraphRun pipeline.

## Policy version history (2024–2026)

| Version | Effective | Superseded by | Notes |
|---|---|---|---|
| 2024.3 | 2024-03-01 | 2024.9 | Initial attestation domain GRAPHRUN.ATTEST.v1 |
| 2024.9 | 2024-09-15 | 2025.6 | Added graph/run canonical separators |
| 2025.6 | 2025-06-01 | 2025.12 | Introduced callback replay semantics |
| 2025.12 | 2025-12-01 | 2026.1 | Emergency signing window (superseded) |
| 2026.1 | 2026-01-05 | — | Current authoritative production policy |

### Supersession notice

Emergency policy **2025.12** was superseded by **2026.1** effective
**2026-01-05T00:00:00Z**. Recovery of **2025.12** commits is forbidden for
production attestations after that instant.

### 2026.1 approval roster

- alice@example.com
- bob@example.com

Approval window for **2026.1**: **2026-01-05** to **2026-03-01** (UTC, inclusive).

### Key rotation notices

- `signer-2025` active until 2026-01-01; overlap permitted for backfill only.
- `signer-2026` active from 2026-01-01 through 2027-01-01.
- `emergency-signer` revoked with supersession of **2025.12**.

## Incident INF-4412

A history rewrite on the deploy branch removed `config/signing-policy.yaml` from
`HEAD` while preserving unreachable commits and reflogs. Authoritative recovery
requires matching a single **2026.1** commit with `Approved-By: alice@example.com`
timestamped inside the **2026.1** window. See fragment `incident-INF-4412.md`.


# Incident INF-4412 — lost policy after history rewrite

During the March 2026 deploy branch cleanup, `config/signing-policy.yaml` was removed from `HEAD` while unreachable commits and reflog entries were preserved for forensic recovery.

Operators must not trust recency-based recovery. Cross-reference candidate commit IDs documented in `config/POLICY_BOOTSTRAP.md` with this manual's approval roster and supersession tables.

Authorized recovery target: policy version **2026.1** with `Approved-By: alice@example.com` inside the **2026.1** approval window.

Unauthorized examples preserved for negative testing:

- **2025.12** emergency policy (superseded)
- **2026.99** permissive draft (`Approved-By: nobody@example.com`)


# Policy roster fragment — authoritative 2026.1 window

The **2026.1** approval roster includes:

- alice@example.com (primary approver)
- bob@example.com (secondary approver)

Approval window for **2026.1**: **2026-01-05** through **2026-03-01** (exclusive end not applicable; both bounds inclusive UTC).

Commits carrying `config/signing-policy.yaml` for version **2026.1** must include an `Approved-By:` trailer naming a roster principal and must be timestamped inside this window.

Supersession: emergency policy **2025.12** was superseded by **2026.1** effective **2026-01-05T00:00:00Z**.


## Appendix APP-00001

### Scope
Operational appendix APP-00001 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00002

### Scope
Operational appendix APP-00002 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00003

### Scope
Operational appendix APP-00003 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00004

### Scope
Operational appendix APP-00004 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00005

### Scope
Operational appendix APP-00005 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00006

### Scope
Operational appendix APP-00006 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00007

### Scope
Operational appendix APP-00007 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00008

### Scope
Operational appendix APP-00008 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00009

### Scope
Operational appendix APP-00009 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00010

### Scope
Operational appendix APP-00010 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00011

### Scope
Operational appendix APP-00011 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00012

### Scope
Operational appendix APP-00012 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00013

### Scope
Operational appendix APP-00013 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00014

### Scope
Operational appendix APP-00014 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00015

### Scope
Operational appendix APP-00015 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00016

### Scope
Operational appendix APP-00016 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00017

### Scope
Operational appendix APP-00017 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00018

### Scope
Operational appendix APP-00018 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00019

### Scope
Operational appendix APP-00019 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00020

### Scope
Operational appendix APP-00020 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00021

### Scope
Operational appendix APP-00021 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00022

### Scope
Operational appendix APP-00022 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00023

### Scope
Operational appendix APP-00023 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00024

### Scope
Operational appendix APP-00024 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00025

### Scope
Operational appendix APP-00025 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00026

### Scope
Operational appendix APP-00026 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00027

### Scope
Operational appendix APP-00027 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00028

### Scope
Operational appendix APP-00028 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00029

### Scope
Operational appendix APP-00029 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00030

### Scope
Operational appendix APP-00030 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00031

### Scope
Operational appendix APP-00031 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00032

### Scope
Operational appendix APP-00032 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00033

### Scope
Operational appendix APP-00033 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00034

### Scope
Operational appendix APP-00034 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00035

### Scope
Operational appendix APP-00035 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00036

### Scope
Operational appendix APP-00036 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00037

### Scope
Operational appendix APP-00037 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00038

### Scope
Operational appendix APP-00038 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00039

### Scope
Operational appendix APP-00039 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00040

### Scope
Operational appendix APP-00040 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00041

### Scope
Operational appendix APP-00041 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00042

### Scope
Operational appendix APP-00042 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00043

### Scope
Operational appendix APP-00043 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00044

### Scope
Operational appendix APP-00044 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00045

### Scope
Operational appendix APP-00045 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00046

### Scope
Operational appendix APP-00046 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00047

### Scope
Operational appendix APP-00047 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00048

### Scope
Operational appendix APP-00048 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00049

### Scope
Operational appendix APP-00049 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00050

### Scope
Operational appendix APP-00050 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00051

### Scope
Operational appendix APP-00051 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00052

### Scope
Operational appendix APP-00052 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00053

### Scope
Operational appendix APP-00053 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00054

### Scope
Operational appendix APP-00054 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00055

### Scope
Operational appendix APP-00055 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00056

### Scope
Operational appendix APP-00056 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00057

### Scope
Operational appendix APP-00057 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00058

### Scope
Operational appendix APP-00058 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00059

### Scope
Operational appendix APP-00059 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00060

### Scope
Operational appendix APP-00060 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00061

### Scope
Operational appendix APP-00061 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00062

### Scope
Operational appendix APP-00062 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00063

### Scope
Operational appendix APP-00063 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00064

### Scope
Operational appendix APP-00064 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00065

### Scope
Operational appendix APP-00065 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00066

### Scope
Operational appendix APP-00066 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00067

### Scope
Operational appendix APP-00067 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00068

### Scope
Operational appendix APP-00068 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00069

### Scope
Operational appendix APP-00069 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00070

### Scope
Operational appendix APP-00070 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00071

### Scope
Operational appendix APP-00071 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00072

### Scope
Operational appendix APP-00072 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00073

### Scope
Operational appendix APP-00073 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00074

### Scope
Operational appendix APP-00074 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00075

### Scope
Operational appendix APP-00075 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00076

### Scope
Operational appendix APP-00076 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00077

### Scope
Operational appendix APP-00077 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00078

### Scope
Operational appendix APP-00078 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00079

### Scope
Operational appendix APP-00079 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00080

### Scope
Operational appendix APP-00080 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00081

### Scope
Operational appendix APP-00081 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00082

### Scope
Operational appendix APP-00082 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00083

### Scope
Operational appendix APP-00083 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00084

### Scope
Operational appendix APP-00084 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00085

### Scope
Operational appendix APP-00085 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00086

### Scope
Operational appendix APP-00086 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00087

### Scope
Operational appendix APP-00087 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00088

### Scope
Operational appendix APP-00088 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00089

### Scope
Operational appendix APP-00089 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00090

### Scope
Operational appendix APP-00090 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00091

### Scope
Operational appendix APP-00091 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00092

### Scope
Operational appendix APP-00092 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00093

### Scope
Operational appendix APP-00093 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00094

### Scope
Operational appendix APP-00094 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00095

### Scope
Operational appendix APP-00095 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00096

### Scope
Operational appendix APP-00096 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00097

### Scope
Operational appendix APP-00097 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00098

### Scope
Operational appendix APP-00098 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00099

### Scope
Operational appendix APP-00099 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00100

### Scope
Operational appendix APP-00100 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00101

### Scope
Operational appendix APP-00101 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00102

### Scope
Operational appendix APP-00102 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00103

### Scope
Operational appendix APP-00103 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00104

### Scope
Operational appendix APP-00104 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00105

### Scope
Operational appendix APP-00105 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00106

### Scope
Operational appendix APP-00106 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00107

### Scope
Operational appendix APP-00107 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00108

### Scope
Operational appendix APP-00108 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00109

### Scope
Operational appendix APP-00109 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00110

### Scope
Operational appendix APP-00110 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00111

### Scope
Operational appendix APP-00111 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00112

### Scope
Operational appendix APP-00112 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00113

### Scope
Operational appendix APP-00113 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00114

### Scope
Operational appendix APP-00114 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00115

### Scope
Operational appendix APP-00115 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00116

### Scope
Operational appendix APP-00116 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00117

### Scope
Operational appendix APP-00117 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00118

### Scope
Operational appendix APP-00118 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00119

### Scope
Operational appendix APP-00119 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00120

### Scope
Operational appendix APP-00120 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00121

### Scope
Operational appendix APP-00121 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00122

### Scope
Operational appendix APP-00122 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00123

### Scope
Operational appendix APP-00123 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00124

### Scope
Operational appendix APP-00124 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00125

### Scope
Operational appendix APP-00125 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00126

### Scope
Operational appendix APP-00126 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00127

### Scope
Operational appendix APP-00127 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00128

### Scope
Operational appendix APP-00128 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00129

### Scope
Operational appendix APP-00129 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00130

### Scope
Operational appendix APP-00130 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00131

### Scope
Operational appendix APP-00131 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00132

### Scope
Operational appendix APP-00132 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00133

### Scope
Operational appendix APP-00133 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00134

### Scope
Operational appendix APP-00134 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00135

### Scope
Operational appendix APP-00135 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00136

### Scope
Operational appendix APP-00136 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00137

### Scope
Operational appendix APP-00137 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00138

### Scope
Operational appendix APP-00138 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00139

### Scope
Operational appendix APP-00139 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00140

### Scope
Operational appendix APP-00140 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00141

### Scope
Operational appendix APP-00141 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00142

### Scope
Operational appendix APP-00142 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00143

### Scope
Operational appendix APP-00143 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00144

### Scope
Operational appendix APP-00144 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00145

### Scope
Operational appendix APP-00145 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00146

### Scope
Operational appendix APP-00146 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00147

### Scope
Operational appendix APP-00147 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00148

### Scope
Operational appendix APP-00148 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00149

### Scope
Operational appendix APP-00149 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00150

### Scope
Operational appendix APP-00150 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00151

### Scope
Operational appendix APP-00151 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00152

### Scope
Operational appendix APP-00152 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00153

### Scope
Operational appendix APP-00153 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00154

### Scope
Operational appendix APP-00154 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00155

### Scope
Operational appendix APP-00155 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00156

### Scope
Operational appendix APP-00156 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00157

### Scope
Operational appendix APP-00157 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00158

### Scope
Operational appendix APP-00158 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00159

### Scope
Operational appendix APP-00159 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00160

### Scope
Operational appendix APP-00160 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00161

### Scope
Operational appendix APP-00161 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00162

### Scope
Operational appendix APP-00162 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00163

### Scope
Operational appendix APP-00163 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00164

### Scope
Operational appendix APP-00164 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00165

### Scope
Operational appendix APP-00165 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00166

### Scope
Operational appendix APP-00166 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00167

### Scope
Operational appendix APP-00167 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00168

### Scope
Operational appendix APP-00168 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00169

### Scope
Operational appendix APP-00169 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00170

### Scope
Operational appendix APP-00170 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00171

### Scope
Operational appendix APP-00171 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00172

### Scope
Operational appendix APP-00172 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00173

### Scope
Operational appendix APP-00173 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00174

### Scope
Operational appendix APP-00174 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00175

### Scope
Operational appendix APP-00175 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00176

### Scope
Operational appendix APP-00176 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00177

### Scope
Operational appendix APP-00177 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00178

### Scope
Operational appendix APP-00178 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00179

### Scope
Operational appendix APP-00179 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00180

### Scope
Operational appendix APP-00180 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00181

### Scope
Operational appendix APP-00181 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00182

### Scope
Operational appendix APP-00182 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00183

### Scope
Operational appendix APP-00183 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00184

### Scope
Operational appendix APP-00184 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00185

### Scope
Operational appendix APP-00185 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00186

### Scope
Operational appendix APP-00186 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00187

### Scope
Operational appendix APP-00187 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00188

### Scope
Operational appendix APP-00188 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00189

### Scope
Operational appendix APP-00189 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00190

### Scope
Operational appendix APP-00190 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00191

### Scope
Operational appendix APP-00191 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00192

### Scope
Operational appendix APP-00192 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00193

### Scope
Operational appendix APP-00193 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00194

### Scope
Operational appendix APP-00194 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00195

### Scope
Operational appendix APP-00195 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00196

### Scope
Operational appendix APP-00196 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00197

### Scope
Operational appendix APP-00197 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00198

### Scope
Operational appendix APP-00198 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00199

### Scope
Operational appendix APP-00199 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00200

### Scope
Operational appendix APP-00200 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00201

### Scope
Operational appendix APP-00201 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00202

### Scope
Operational appendix APP-00202 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00203

### Scope
Operational appendix APP-00203 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00204

### Scope
Operational appendix APP-00204 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00205

### Scope
Operational appendix APP-00205 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00206

### Scope
Operational appendix APP-00206 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00207

### Scope
Operational appendix APP-00207 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00208

### Scope
Operational appendix APP-00208 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00209

### Scope
Operational appendix APP-00209 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00210

### Scope
Operational appendix APP-00210 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00211

### Scope
Operational appendix APP-00211 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00212

### Scope
Operational appendix APP-00212 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00213

### Scope
Operational appendix APP-00213 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00214

### Scope
Operational appendix APP-00214 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00215

### Scope
Operational appendix APP-00215 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00216

### Scope
Operational appendix APP-00216 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00217

### Scope
Operational appendix APP-00217 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00218

### Scope
Operational appendix APP-00218 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00219

### Scope
Operational appendix APP-00219 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00220

### Scope
Operational appendix APP-00220 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00221

### Scope
Operational appendix APP-00221 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00222

### Scope
Operational appendix APP-00222 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00223

### Scope
Operational appendix APP-00223 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00224

### Scope
Operational appendix APP-00224 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00225

### Scope
Operational appendix APP-00225 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00226

### Scope
Operational appendix APP-00226 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00227

### Scope
Operational appendix APP-00227 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00228

### Scope
Operational appendix APP-00228 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00229

### Scope
Operational appendix APP-00229 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00230

### Scope
Operational appendix APP-00230 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00231

### Scope
Operational appendix APP-00231 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00232

### Scope
Operational appendix APP-00232 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00233

### Scope
Operational appendix APP-00233 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00234

### Scope
Operational appendix APP-00234 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00235

### Scope
Operational appendix APP-00235 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00236

### Scope
Operational appendix APP-00236 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00237

### Scope
Operational appendix APP-00237 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00238

### Scope
Operational appendix APP-00238 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00239

### Scope
Operational appendix APP-00239 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00240

### Scope
Operational appendix APP-00240 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00241

### Scope
Operational appendix APP-00241 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00242

### Scope
Operational appendix APP-00242 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00243

### Scope
Operational appendix APP-00243 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00244

### Scope
Operational appendix APP-00244 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00245

### Scope
Operational appendix APP-00245 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00246

### Scope
Operational appendix APP-00246 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00247

### Scope
Operational appendix APP-00247 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00248

### Scope
Operational appendix APP-00248 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00249

### Scope
Operational appendix APP-00249 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00250

### Scope
Operational appendix APP-00250 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00251

### Scope
Operational appendix APP-00251 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00252

### Scope
Operational appendix APP-00252 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00253

### Scope
Operational appendix APP-00253 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00254

### Scope
Operational appendix APP-00254 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00255

### Scope
Operational appendix APP-00255 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00256

### Scope
Operational appendix APP-00256 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00257

### Scope
Operational appendix APP-00257 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00258

### Scope
Operational appendix APP-00258 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00259

### Scope
Operational appendix APP-00259 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00260

### Scope
Operational appendix APP-00260 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 2
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00261

### Scope
Operational appendix APP-00261 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 3
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00262

### Scope
Operational appendix APP-00262 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 4
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00263

### Scope
Operational appendix APP-00263 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 5
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00264

### Scope
Operational appendix APP-00264 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 6
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 0
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00265

### Scope
Operational appendix APP-00265 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 7
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 1
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


## Appendix APP-00266

### Scope
Operational appendix APP-00266 documents enforcement checklist items for GraphRunSigner
policy version **2026.1** and historical superseded releases.

### Approval cross-reference
- Roster principals: alice@example.com, bob@example.com
- Window: 2026-01-05 .. 2026-03-01 UTC
- Supersedes emergency **2025.12** per table in §Policy version history

### Rule bundle 1
1. Reject built-in permissive fallback policies for signing.
2. Verify MLflow tarball SHA-256 on every cache use.
3. Pin fetch origin; reject external redirect targets.
4. Canonicalize graphs per GRAPHRUN.GRAPH.v1 before digest.
5. Canonicalize runs per GRAPHRUN.RUN.v1 without wall-clock fields.
6. Validate callbacks against extracted MLflow schema; terminal states require artifact_digest.
7. Recover policy via reflog/unreachable objects; recency alone is not authoritative.

### Incident tie-in INF-4412
Candidate commit messages must include `Approved-By:` trailers. Unauthorized permissive
**2026.99** drafts (`Approved-By: nobody@example.com`) must be discarded even if newer.

### Rotation note 2
Key `signer-2026` is the default active signer for runs started on or after 2026-01-01.


---

Document generated with 266 structured appendices. Authoritative policy recovery reference: **2026.1** / alice@example.com / approval window 2026-01-05..2026-03-01; superseded emergency **2025.12**; incident **INF-4412**.

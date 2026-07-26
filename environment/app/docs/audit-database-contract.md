# Current-state service deployment audit database

The audit database is a deterministic current-state artifact, not an event log. It contains exactly nine user tables, created in this order.

`deployment_run(run_id TEXT PRIMARY KEY, site_key TEXT NOT NULL, handbook_revision TEXT NOT NULL, catalog_generation INTEGER NOT NULL CHECK(catalog_generation>0), change_generation INTEGER NOT NULL CHECK(change_generation>0), request_set_sha256 TEXT NOT NULL CHECK(length(request_set_sha256)=64), evidence_set_sha256 TEXT NOT NULL CHECK(length(evidence_set_sha256)=64), catalog_snapshot_sha256 TEXT NOT NULL CHECK(length(catalog_snapshot_sha256)=64), change_snapshot_sha256 TEXT NOT NULL CHECK(length(change_snapshot_sha256)=64), authorization_digest TEXT NOT NULL CHECK(length(authorization_digest)=64), status TEXT NOT NULL CHECK(status='commissioned'))`

`input_artifact(kind TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL CHECK(length(sha256)=64), bytes INTEGER NOT NULL CHECK(bytes>=0), PRIMARY KEY(kind,path))`

`configuration(key TEXT PRIMARY KEY, value TEXT NOT NULL, source_code TEXT NOT NULL CHECK(source_code IN ('CTX','ALIAS','SOCK','LIMIT','ROUTE','META','PATH')))`

`route(method TEXT NOT NULL, external_path TEXT NOT NULL, upstream TEXT NOT NULL, auth_mode TEXT NOT NULL, timeout_ms INTEGER NOT NULL CHECK(timeout_ms>0), source_route_id TEXT NOT NULL, cohort_code TEXT NOT NULL, decision_code TEXT NOT NULL CHECK(decision_code IN ('selected','replaced','required')), PRIMARY KEY(method,external_path))`

`decision(sequence INTEGER PRIMARY KEY CHECK(sequence>0), domain TEXT NOT NULL, subject TEXT NOT NULL, outcome TEXT NOT NULL CHECK(outcome IN ('selected','rejected','replaced','withdrawn','required','calculated','validated')), rule_ref TEXT NOT NULL, evidence TEXT NOT NULL)`

`assertion(name TEXT PRIMARY KEY, passed INTEGER NOT NULL CHECK(passed IN (0,1)), observed TEXT NOT NULL, rule_ref TEXT NOT NULL)`

`authorization(ticket_id TEXT PRIMARY KEY, change_generation INTEGER NOT NULL CHECK(change_generation>0), activation_id TEXT NOT NULL, release_lane TEXT NOT NULL, quorum_required INTEGER NOT NULL CHECK(quorum_required>0), quorum_observed INTEGER NOT NULL CHECK(quorum_observed>=quorum_required), authorization_digest TEXT NOT NULL CHECK(length(authorization_digest)=64), activation_token TEXT NOT NULL CHECK(length(activation_token)=24))`

`approval(exclusive_group TEXT NOT NULL, approver_id TEXT NOT NULL, role_code TEXT NOT NULL, weight INTEGER NOT NULL CHECK(weight>0), state TEXT NOT NULL CHECK(state IN ('approve','reinstate')), event_id TEXT NOT NULL, PRIMARY KEY(exclusive_group,approver_id,role_code))`

`publication_file(path TEXT PRIMARY KEY, sha256 TEXT NOT NULL CHECK(length(sha256)=64), bytes INTEGER NOT NULL CHECK(bytes>=0), mode_text TEXT NOT NULL CHECK(mode_text IN ('0640','0600')))`

## Required current-state rows

`deployment_run` has one commissioned row. `input_artifact` has exactly nine rows using the exact kinds and paths in the publication contract. `configuration` contains 14 text-valued keys. `route` mirrors routes.map. `assertion` contains all fifteen rules once with integer `passed=1`. `authorization` contains one row matching the activation seal. `approval` contains exactly the two quorum-contributing approvals in seal order. `publication_file` contains exactly six published paths. The persistent lock is excluded.

The decision table contains exactly 20 rows with contiguous sequence numbers 1 through 20:

1. identity alias selection;
2–6. five rejected socket candidates;
7. selected socket candidate;
8. selected route-family rule;
9. required-route directive;
10. replacement directive;
11. withdrawal directive;
12. completed route closure;
13. descriptor/connection calculation;
14. body-envelope and tier calculation;
15. selected change ticket;
16. selected operations-group approval;
17. selected security-group approval;
18. rejected lower-weight same-group approval;
19. weighted distinct-group quorum calculation;
20. selected activation candidate.

Rows 2–7 use domain exactly `socket`; the EACCES rejection evidence equals exactly `last=EACCES`. Rows 15–20 use domain exactly `change-control`. Row 18 has outcome `rejected` and identifies the non-contributing SRE approval. The approval event after the sealed timestamp does not create a decision row. Duplicate calculations, individual assertion checks, publication writes, and file-mode checks do not create additional rows.

Rows are inserted in deterministic key order. Configuration, route, authorization, approval, and publication tables reconcile exactly with the published files. Digest columns use the profiles in the operator and change-control contracts. The SQLite file must be byte-identical on repeated commissioning from unchanged inputs.

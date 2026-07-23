# Current-state repair audit database

The audit database is a deterministic current-state artifact, not an event log. It contains exactly seven user tables, created in this order.

`repair_run(run_id TEXT PRIMARY KEY, site_key TEXT NOT NULL, handbook_revision TEXT NOT NULL, catalog_generation INTEGER NOT NULL CHECK(catalog_generation>0), request_set_sha256 TEXT NOT NULL CHECK(length(request_set_sha256)=64), evidence_set_sha256 TEXT NOT NULL CHECK(length(evidence_set_sha256)=64), catalog_snapshot_sha256 TEXT NOT NULL CHECK(length(catalog_snapshot_sha256)=64), status TEXT NOT NULL CHECK(status='applied'))`

`input_artifact(kind TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL CHECK(length(sha256)=64), bytes INTEGER NOT NULL CHECK(bytes>=0), PRIMARY KEY(kind,path))`

`configuration(key TEXT PRIMARY KEY, value TEXT NOT NULL, source_code TEXT NOT NULL CHECK(source_code IN ('CTX','ALIAS','SOCK','LIMIT','ROUTE','META','PATH')))`

`route(method TEXT NOT NULL, external_path TEXT NOT NULL, upstream TEXT NOT NULL, auth_mode TEXT NOT NULL, timeout_ms INTEGER NOT NULL CHECK(timeout_ms>0), source_route_id TEXT NOT NULL, cohort_code TEXT NOT NULL, decision_code TEXT NOT NULL CHECK(decision_code IN ('selected','replaced','required')), PRIMARY KEY(method,external_path))`

`decision(sequence INTEGER PRIMARY KEY CHECK(sequence>0), domain TEXT NOT NULL, subject TEXT NOT NULL, outcome TEXT NOT NULL CHECK(outcome IN ('selected','rejected','replaced','withdrawn','required','calculated','validated')), rule_ref TEXT NOT NULL, evidence TEXT NOT NULL)`

`assertion(name TEXT PRIMARY KEY, passed INTEGER NOT NULL CHECK(passed IN (0,1)), observed TEXT NOT NULL, rule_ref TEXT NOT NULL)`

`publication_file(path TEXT PRIMARY KEY, sha256 TEXT NOT NULL CHECK(length(sha256)=64), bytes INTEGER NOT NULL CHECK(bytes>=0), mode_text TEXT NOT NULL CHECK(mode_text IN ('0640','0600')))`

## Required current-state rows

`repair_run` has exactly one applied row. `input_artifact` has exactly eight rows and uses the exact kinds and paths defined by the publication contract, including the literal kind `catalog-batch-result`. `configuration` contains the 14 keys in the publication contract and stores all values as text. `route` mirrors routes.map. `assertion` contains each of the ten catalog audit rules exactly once, with integer `passed=1`. `publication_file` contains exactly the five published paths; its column is named `mode_text`, while the corresponding JSON key is `mode`. The required empty lock at `/app/var/harbor-repair.lock` is excluded because it is a persistent coordination artifact rather than generation content. It must still exist after recovery with mode `0600`.

The decision table is a deliberately bounded material-decision summary, not a dump of every examined row. It contains exactly 14 rows with contiguous sequence numbers 1 through 14 and no additional informational rows. The required sequence profile is:

1. identity alias selection;
2–6. the five rejected socket candidates, one row per candidate;
7. selected socket candidate;
8. selected route-family rule;
9. required-route directive;
10. replacement directive;
11. withdrawal directive;
12. completed route-closure validation;
13. descriptor/connection-limit calculation;
14. request-body envelope and tier calculation.

Socket rejection caused by the final exact-path syscall must preserve evidence `last=EACCES`. The replacement and withdrawal rows use domain `route-directive` and outcomes `replaced` and `withdrawn`. Dependency-added routes are represented in the route table through `decision_code='required'`; they do not create extra decision rows beyond the route-closure row. Candidate ranks, duplicate calculations, individual assertion checks, publication writes, and file-mode checks likewise do not create additional decision rows.

Rows are inserted in deterministic key order. The configuration and route tables reconcile exactly with the text outputs. The digest columns in `repair_run` use the newline-sensitive digest profile from `/app/docs/operator-recovery-contract.md`. The resulting SQLite file must be byte-identical on repeated recovery from unchanged inputs.

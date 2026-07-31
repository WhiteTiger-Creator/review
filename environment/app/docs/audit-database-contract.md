# Commissioning ledger database

`/app/var/commissioning-ledger.db` is a deterministic current-state SQLite database with exactly nine user tables in this order:

`commissioning_run(run_id TEXT PRIMARY KEY, site_key TEXT NOT NULL, handbook_revision TEXT NOT NULL, catalog_generation INTEGER NOT NULL CHECK(catalog_generation>0), schedule_generation INTEGER NOT NULL CHECK(schedule_generation>0), request_set_sha256 TEXT NOT NULL CHECK(length(request_set_sha256)=64), record_set_sha256 TEXT NOT NULL CHECK(length(record_set_sha256)=64), catalog_snapshot_sha256 TEXT NOT NULL CHECK(length(catalog_snapshot_sha256)=64), schedule_snapshot_sha256 TEXT NOT NULL CHECK(length(schedule_snapshot_sha256)=64), readiness_digest TEXT NOT NULL CHECK(length(readiness_digest)=64), status TEXT NOT NULL CHECK(status='commissioned'))`

`input_artifact(kind TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL CHECK(length(sha256)=64), bytes INTEGER NOT NULL CHECK(bytes>=0), PRIMARY KEY(kind,path))`

`configuration(key TEXT PRIMARY KEY, value TEXT NOT NULL, source_code TEXT NOT NULL CHECK(source_code IN ('CTX','ALIAS','SOCK','LIMIT','ROUTE','META','PATH')))`

`route(method TEXT NOT NULL, external_path TEXT NOT NULL, upstream TEXT NOT NULL, auth_mode TEXT NOT NULL, timeout_ms INTEGER NOT NULL CHECK(timeout_ms>0), source_route_id TEXT NOT NULL, cohort_code TEXT NOT NULL, decision_code TEXT NOT NULL CHECK(decision_code IN ('selected','replaced','required')), PRIMARY KEY(method,external_path))`

`decision(sequence INTEGER PRIMARY KEY CHECK(sequence>0), domain TEXT NOT NULL, subject TEXT NOT NULL, outcome TEXT NOT NULL CHECK(outcome IN ('selected','rejected','replaced','withdrawn','required','calculated','validated')), rule_ref TEXT NOT NULL, evidence TEXT NOT NULL)`

`assertion(name TEXT PRIMARY KEY, passed INTEGER NOT NULL CHECK(passed IN (0,1)), observed TEXT NOT NULL, rule_ref TEXT NOT NULL)`

`window_plan(order_id TEXT PRIMARY KEY, schedule_generation INTEGER NOT NULL CHECK(schedule_generation>0), slot_id TEXT NOT NULL, service_lane TEXT NOT NULL, ack_weight_required INTEGER NOT NULL CHECK(ack_weight_required>0), ack_weight_observed INTEGER NOT NULL CHECK(ack_weight_observed>=ack_weight_required), readiness_digest TEXT NOT NULL CHECK(length(readiness_digest)=64), launch_token TEXT NOT NULL CHECK(length(launch_token)=24))`

`acknowledgment(work_group TEXT NOT NULL, operator_id TEXT NOT NULL, role_code TEXT NOT NULL, weight INTEGER NOT NULL CHECK(weight>0), state TEXT NOT NULL CHECK(state IN ('acknowledge','restore')), event_id TEXT NOT NULL, PRIMARY KEY(work_group,operator_id,role_code))`

`publication_file(path TEXT PRIMARY KEY, sha256 TEXT NOT NULL CHECK(length(sha256)=64), bytes INTEGER NOT NULL CHECK(bytes>=0), mode_text TEXT NOT NULL CHECK(mode_text IN ('0640','0600','0644')))`

The tables contain one run, nine inputs, fourteen configuration rows, four routes, fifteen passing assertions, one window plan, two contributing acknowledgments, seven publication rows, and exactly twenty contiguous decisions. Decisions 2–7 have domain `socket`; decision 3 has evidence exactly `last=EACCES`. Decisions 15–20 have domain `maintenance-window`. Decision 18 identifies the non-contributing SRE acknowledgment: its `subject` is exactly the bare `operator_id` alone, `carol.sre`. Do not concatenate `work_group` or `role_code`, and do not substitute the acknowledgment `event_id`. Repeated commissioning from unchanged inputs produces a byte-identical database.

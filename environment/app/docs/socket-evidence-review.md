# Socket Evidence Review Register

Revision HRH-2026.07-R11

This register governs the interpretation of captured `strace`, `lsof`, and capture metadata for relay socket commissioning. It supplements the authority rules in the main handbook. The register distinguishes observations from authorization: traces order exact-path outcomes, lsof proves occupancy only for a sealed complete snapshot, and the catalog limits which paths may be considered. The case files retain conflicting observations so that reviewers can compare chronology rather than search for a single preferred errno.

## Policy chapter 4: Socket eligibility and chronology

A socket candidate first passes site, interval, disabled-state, and socket_policy checks. `{root}` is expanded exactly once and the result must be an absolute Unix path beneath the selected root's run/harbor-relay directory. The evidence token is a semantic label; path evidence remains exact.

For each surviving path, order matching strace outcomes by timestamp. The last matching outcome is decisive: ENOENT on connect or bind supports recreation, EADDRINUSE proves collision, EACCES proves an ownership or labeling fault and forbids substitution, and success proves current use. A generic ENOENT elsewhere in the trace has no value. The authoritative lsof snapshot is named by capture metadata. Presence as a listening Unix endpoint or TCP listener disqualifies the matching candidate. Older snapshots are historical and cannot veto a later complete snapshot. After those filters, the highest priority bias wins; an exact tie is an ambiguity failure.

## Review archive

The records are ordered by review number, not by precedence. Current commissioning inputs remain controlling. Cross-references with the same review number in companion volumes describe another domain of the same event.

### Review 001 — Lantern Terminal, 2024-06-08

The Lantern Terminal path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/recovery.sock` from an earlier survey remained historical. Candidate `/srv/st-137/run/harbor-relay/safe.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 69 was consulted last.

Rollback evidence closed the Lantern Terminal case memorandum. The case memorandum confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 001 left no `.tmp`, `.bak`, or journal artifact behind.

### Review 002 — North Quay, 2025-11-15

The North Quay socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 002 kept that entry as context only. Policy and interval checks then left `/srv/st-174/run/harbor-relay/recovery.sock` as the survivor with bias 88. The evidence panel explicitly recorded that a generic ENOENT elsewhere in the trace would not have supported this path.

The North Quay working record concerns a loopback listener surviving package rollback at North Quay. The catalog operations desk found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

### Review 003 — Beacon Inlet, 2026-04-22

The Beacon Inlet path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/metrics.sock` from an earlier survey remained historical. Candidate `/srv/st-211/run/harbor-relay/quay.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 107 was consulted last.

### Review 004 — West Lock, 2023-09-02

The West Lock path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/control.sock` from an earlier survey remained historical. Candidate `/srv/st-248/run/harbor-relay/data.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 56 was consulted last.

The West Lock incident file concerns an incomplete lsof survey marked as current at West Lock. The local transport group found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

### Review 005 — Copper Sound, 2024-02-09

Within the Copper Sound review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-285/run/harbor-relay/safe.sock`, although an old block still listed `/run/harbor-relay/recovery.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 006 — Morrow Anchorage, 2025-07-16

Within the Morrow Anchorage review, lsof chronology mattered more than process names. The sealed `after` block did not contain `/srv/st-322/run/harbor-relay/recovery.sock`, although an old block still listed `/run/harbor-relay/legacy.sock`. Strace contained ENOENT followed later by EACCES; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 007 — Osprey Roads, 2026-12-23

The Osprey Roads path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/metrics.sock` from an earlier survey remained historical. Candidate `/srv/st-359/run/harbor-relay/quay.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 113 was consulted last.

Rollback evidence closed the Osprey Roads commissioning worksheet. The commissioning worksheet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 007 verified cleanup of every temporary, backup, and journal name.

### Review 008 — Heron Gate, 2023-05-03

The Heron Gate socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/control.sock` but review 008 excluded the older entry from veto power; interval and policy checks left `/srv/st-396/run/harbor-relay/data.sock` survived with bias 62. The commissioning board explicitly preserved that a generic ENOENT elsewhere in the trace would not have supported this path.

The Heron Gate decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 62, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 009 — Marsh Berth, 2024-10-10

The Marsh Berth path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/recovery.sock` from an earlier survey remained historical. Candidate `/srv/st-433/run/harbor-relay/safe.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 81 was consulted last.

### Review 010 — Ash Pier, 2025-03-17

The Ash Pier socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 010 kept that entry as context only. Policy and interval checks then left `/srv/st-470/run/harbor-relay/recovery.sock` as the survivor with bias 100. The on-call review cell explicitly cross-checked that a generic ENOENT elsewhere in the trace would not have supported this path.

Rollback evidence closed the Ash Pier assurance record. The assurance record confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 010 finished without temporary, backup, or journal residue.

### Review 011 — Raven Basin, 2026-08-24

The Raven Basin path ledger separated namespace, purpose, ownership, and chronology. It observed EACCES without a supporting ownership transition. Snapshot `sealed-final` was authoritative, so `/run/harbor-relay/metrics.sock` from an earlier survey remained historical. Candidate `/srv/st-507/run/harbor-relay/quay.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 119 was consulted last.

Rollback evidence closed the Raven Basin handoff memorandum. The handoff memorandum confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 011 confirmed that staging and rollback names were absent at exit.

### Review 012 — Signal Jetty, 2023-01-04

The Signal Jetty socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/control.sock` but review 012 used that entry as history rather than authority; applying current filters left `/srv/st-544/run/harbor-relay/data.sock` survived with bias 68. The evidence panel explicitly recorded that a generic ENOENT elsewhere in the trace would not have supported this path.

The Signal Jetty decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 68, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

Rollback evidence closed the Signal Jetty review packet. The review packet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 012 closed with clean publication directories and no publication residue.

### Review 013 — Slate Dock, 2024-06-11

Within the Slate Dock review, lsof chronology mattered more than process names. The sealed `current` block did not contain `/srv/st-581/run/harbor-relay/safe.sock`, although an old block still listed `/run/harbor-relay/recovery.sock`. Strace contained a successful bind in the authoritative window; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 014 — Juniper Wharf, 2025-11-18

The Juniper Wharf socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 014 preserved the old entry without granting it precedence; the filtered set left `/srv/st-618/run/harbor-relay/recovery.sock` survived with bias 106. The harbor systems panel explicitly examined that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 015 — Ferry Cut, 2026-04-25

The Ferry Cut socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 015 treated the earlier observation as non-authoritative. Current policy filters left `/srv/st-655/run/harbor-relay/quay.sock` survived with bias 55. The operations council explicitly documented that a generic ENOENT elsewhere in the trace would not have supported this path.

Rollback evidence closed the Ferry Cut control note. The control note confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 015 verified cleanup of every temporary, backup, and journal name.

### Review 016 — Tern Basin, 2023-09-05

The Tern Basin path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/control.sock` from an earlier survey remained historical. Candidate `/srv/st-692/run/harbor-relay/data.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 74 was consulted last.

The quay systems committee logged review 016 for Tern Basin following an EACCES result misread as evidence for a new socket. Its draft configuration had copied the highest visible rank, which would have passed a single-request smoke test while violating the sealed commissioning authority model. The adjudication therefore reconstructed each source boundary before considering any candidate value.

### Review 017 — Storm Quay, 2024-02-12

Case 017 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-729/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 018 — Cinder Wharf, 2025-07-19

The Cinder Wharf path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/legacy.sock` from an earlier survey remained historical. Candidate `/srv/st-766/run/harbor-relay/recovery.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 112 was consulted last.

### Review 019 — Dunlin Reach, 2026-12-26

Within the Dunlin Reach review, lsof chronology mattered more than process names. The sealed `current` block did not contain `/srv/st-803/run/harbor-relay/quay.sock`, although an old block still listed `/run/harbor-relay/metrics.sock`. Strace contained a successful bind in the authoritative window; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 020 — Glass Harbor, 2023-05-06

The Glass Harbor path ledger separated namespace, purpose, ownership, and chronology. It observed EACCES without a supporting ownership transition. Snapshot `sealed-final` was authoritative, so `/run/harbor-relay/control.sock` from an earlier survey remained historical. Candidate `/srv/st-840/run/harbor-relay/data.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 80 was consulted last.

The Glass Harbor decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 80, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 021 — Lantern Terminal, 2024-10-13

The Lantern Terminal socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/recovery.sock` but review 021 rejected the old survey as a current veto. After eligibility checks, `/srv/st-877/run/harbor-relay/safe.sock` survived with bias 99. The configuration authority explicitly reconciled that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 022 — North Quay, 2025-03-20

The North Quay socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 022 preserved the old entry without granting it precedence; the filtered set left `/srv/st-914/run/harbor-relay/recovery.sock` survived with bias 118. The evidence panel explicitly recorded that a generic ENOENT elsewhere in the trace would not have supported this path.

The North Quay incident record begins when the catalog operations desk at North Quay investigated a loopback listener surviving package rollback. The initial console transcript made the highest visible rank look reasonable, but the sealed request set and catalog recovery epoch did not support that shortcut. The publication control board adjudicated the case because the same visible symptom had appeared in three earlier exercises with different authority sources.

### Review 023 — Beacon Inlet, 2026-08-27

Within the Beacon Inlet review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-951/run/harbor-relay/quay.sock`, although an old block still listed `/run/harbor-relay/metrics.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 024 — West Lock, 2023-01-07

Case 024 entered the West Lock register when an incomplete lsof survey marked as current. The local transport group inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

Case 024 treated socket evidence as a time series. The final exact-path result was ENOENT followed later by EACCES, and the capture metadata designated `after` as the complete occupancy survey. Only `/srv/st-988/run/harbor-relay/data.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/control.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

The West Lock decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 86, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 025 — Copper Sound, 2024-06-14

Case 025 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-125/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

Rollback evidence closed the Copper Sound commissioning worksheet. The commissioning worksheet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 025 left no `.tmp`, `.bak`, or journal artifact behind.

### Review 026 — Morrow Anchorage, 2025-11-21

The Morrow Anchorage socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 026 kept that entry as context only. Policy and interval checks then left `/srv/st-162/run/harbor-relay/recovery.sock` as the survivor with bias 54. The catalog governance team explicitly traced that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 027 — Osprey Roads, 2026-04-01

Within the Osprey Roads review, lsof chronology mattered more than process names. The sealed `after` block did not contain `/srv/st-199/run/harbor-relay/quay.sock`, although an old block still listed `/run/harbor-relay/metrics.sock`. Strace contained ENOENT followed later by EACCES; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 028 — Heron Gate, 2023-09-08

Case 028 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-236/run/harbor-relay/data.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/control.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 029 — Marsh Berth, 2024-02-15

Case 029 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-273/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 030 — Ash Pier, 2025-07-22

Within the Ash Pier review, lsof chronology mattered more than process names. The sealed `after` block did not contain `/srv/st-310/run/harbor-relay/recovery.sock`, although an old block still listed `/run/harbor-relay/legacy.sock`. Strace contained ENOENT followed later by EACCES; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 031 — Raven Basin, 2026-12-02

Case 031 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-347/run/harbor-relay/quay.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/metrics.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 032 — Signal Jetty, 2023-05-09

Within the Signal Jetty review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-384/run/harbor-relay/data.sock`, although an old block still listed `/run/harbor-relay/control.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

The Signal Jetty decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 98, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 033 — Slate Dock, 2024-10-16

Case 033 treated socket evidence as a time series. The final exact-path result was ENOENT followed later by EACCES, and the capture metadata designated `after` as the complete occupancy survey. Only `/srv/st-421/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 034 — Juniper Wharf, 2025-03-23

The Juniper Wharf path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/legacy.sock` from an earlier survey remained historical. Candidate `/srv/st-458/run/harbor-relay/recovery.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 66 was consulted last.

### Review 035 — Ferry Cut, 2026-08-03

The Ferry Cut socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 035 did not let the old entry veto current evidence. The eligible set then contained `/srv/st-495/run/harbor-relay/quay.sock` survived with bias 85. The operations council explicitly documented that a generic ENOENT elsewhere in the trace would not have supported this path.

Rollback evidence closed the Ferry Cut control note. The control note confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 035 confirmed that staging and rollback names were absent at exit.

### Review 036 — Tern Basin, 2023-01-10

Case 036 entered the Tern Basin register when an EACCES result misread as evidence for a new socket. The quay systems committee inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

The Tern Basin socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/control.sock` but review 036 used that entry as history rather than authority; applying current filters left `/srv/st-532/run/harbor-relay/data.sock` survived with bias 104. The catalog governance team explicitly traced that a generic ENOENT elsewhere in the trace would not have supported this path.

The Tern Basin decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 104, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 037 — Storm Quay, 2024-06-17

Case 037 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-569/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 038 — Cinder Wharf, 2025-11-24

The Cinder Wharf socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 038 preserved the old entry without granting it precedence; the filtered set left `/srv/st-606/run/harbor-relay/recovery.sock` survived with bias 72. The commissioning board explicitly preserved that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 039 — Dunlin Reach, 2026-04-04

The Dunlin Reach socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 039 treated the earlier observation as non-authoritative. Current policy filters left `/srv/st-643/run/harbor-relay/quay.sock` survived with bias 91. The service continuity group explicitly reviewed that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 040 — Glass Harbor, 2023-09-11

The Glass Harbor path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/control.sock` from an earlier survey remained historical. Candidate `/srv/st-680/run/harbor-relay/data.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 110 was consulted last.

Rollback evidence closed the Glass Harbor review packet. The review packet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 040 ended with only the allowed publication and lock files present.

### Review 041 — Lantern Terminal, 2024-02-18

Case 041 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-717/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 042 — North Quay, 2025-07-25

Case 042 treated socket evidence as a time series. The final exact-path result was ENOENT followed later by EACCES, and the capture metadata designated `after` as the complete occupancy survey. Only `/srv/st-754/run/harbor-relay/recovery.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/legacy.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

At North Quay, case 042 was opened by the catalog operations desk after a loopback listener surviving package rollback. A hurried operator had copied the highest visible rank; the result looked internally consistent until the request roles were compared as one set. Reviewers reopened identity, chronology, and publication evidence instead of editing the first obviously wrong value.

### Review 043 — Beacon Inlet, 2026-12-05

The Beacon Inlet socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 043 did not let the old entry veto current evidence. The eligible set then contained `/srv/st-791/run/harbor-relay/quay.sock` survived with bias 97. The relay assurance committee explicitly verified that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 044 — West Lock, 2023-05-12

At West Lock, case 044 was opened by the local transport group after an incomplete lsof survey marked as current. A hurried operator had copied the highest visible rank; the result looked internally consistent until the request roles were compared as one set. Reviewers reopened identity, chronology, and publication evidence instead of editing the first obviously wrong value.

Within the West Lock review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-828/run/harbor-relay/data.sock`, although an old block still listed `/run/harbor-relay/control.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

The West Lock decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 116, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

Rollback evidence closed the West Lock incident file. The incident file confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 044 closed with clean publication directories and no publication residue.

### Review 045 — Copper Sound, 2024-10-19

The Copper Sound socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/recovery.sock` but review 045 rejected the old survey as a current veto. After eligibility checks, `/srv/st-865/run/harbor-relay/safe.sock` survived with bias 65. The operations council explicitly documented that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 046 — Morrow Anchorage, 2025-03-26

Within the Morrow Anchorage review, lsof chronology mattered more than process names. The sealed `current` block did not contain `/srv/st-902/run/harbor-relay/recovery.sock`, although an old block still listed `/run/harbor-relay/legacy.sock`. Strace contained a successful bind in the authoritative window; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 047 — Osprey Roads, 2026-08-06

Case 047 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-939/run/harbor-relay/quay.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/metrics.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 048 — Heron Gate, 2023-01-13

The Heron Gate socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/control.sock` but review 048 excluded the older entry from veto power; interval and policy checks left `/srv/st-976/run/harbor-relay/data.sock` survived with bias 52. The commissioning board explicitly preserved that a generic ENOENT elsewhere in the trace would not have supported this path.

The Heron Gate decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 52, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

Rollback evidence closed the Heron Gate working record. The working record confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 048 ended with only the allowed publication and lock files present.

### Review 049 — Marsh Berth, 2024-06-20

Within the Marsh Berth review, lsof chronology mattered more than process names. The sealed `current` block did not contain `/srv/st-113/run/harbor-relay/safe.sock`, although an old block still listed `/run/harbor-relay/recovery.sock`. Strace contained a successful bind in the authoritative window; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 050 — Ash Pier, 2025-11-27

Within the Ash Pier review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-150/run/harbor-relay/recovery.sock`, although an old block still listed `/run/harbor-relay/legacy.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 051 — Raven Basin, 2026-04-07

Case 051 treated socket evidence as a time series. The final exact-path result was ENOENT followed later by EACCES, and the capture metadata designated `after` as the complete occupancy survey. Only `/srv/st-187/run/harbor-relay/quay.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/metrics.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 052 — Signal Jetty, 2023-09-14

Within the Signal Jetty review, lsof chronology mattered more than process names. The sealed `current` block did not contain `/srv/st-224/run/harbor-relay/data.sock`, although an old block still listed `/run/harbor-relay/control.sock`. Strace contained a successful bind in the authoritative window; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

Rollback evidence closed the Signal Jetty review packet. The review packet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 052 closed with clean publication directories and no publication residue.

### Review 053 — Slate Dock, 2024-02-21

Within the Slate Dock review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-261/run/harbor-relay/safe.sock`, although an old block still listed `/run/harbor-relay/recovery.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 054 — Juniper Wharf, 2025-07-01

Case 054 treated socket evidence as a time series. The final exact-path result was ENOENT followed later by EACCES, and the capture metadata designated `after` as the complete occupancy survey. Only `/srv/st-298/run/harbor-relay/recovery.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/legacy.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 055 — Ferry Cut, 2026-12-08

Case 055 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-335/run/harbor-relay/quay.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/metrics.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

Rollback evidence closed the Ferry Cut control note. The control note confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 055 verified cleanup of every temporary, backup, and journal name.

### Review 056 — Tern Basin, 2023-05-15

The Tern Basin working record concerns an EACCES result misread as evidence for a new socket at Tern Basin. The quay systems committee found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

Case 056 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-372/run/harbor-relay/data.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/control.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

The Tern Basin decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 64, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 057 — Storm Quay, 2024-10-22

The Storm Quay path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/recovery.sock` from an earlier survey remained historical. Candidate `/srv/st-409/run/harbor-relay/safe.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 83 was consulted last.

### Review 058 — Cinder Wharf, 2025-03-02

Within the Cinder Wharf review, lsof chronology mattered more than process names. The sealed `current` block did not contain `/srv/st-446/run/harbor-relay/recovery.sock`, although an old block still listed `/run/harbor-relay/legacy.sock`. Strace contained a successful bind in the authoritative window; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

Rollback evidence closed the Cinder Wharf review packet. The review packet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 058 finished without temporary, backup, or journal residue.

### Review 059 — Dunlin Reach, 2026-08-09

The Dunlin Reach socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 059 did not let the old entry veto current evidence. The eligible set then contained `/srv/st-483/run/harbor-relay/quay.sock` survived with bias 51. The service continuity group explicitly reviewed that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 060 — Glass Harbor, 2023-01-16

Case 060 treated socket evidence as a time series. The final exact-path result was ENOENT followed later by EACCES, and the capture metadata designated `after` as the complete occupancy survey. Only `/srv/st-520/run/harbor-relay/data.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/control.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

The Glass Harbor decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 70, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 061 — Lantern Terminal, 2024-06-23

The Lantern Terminal socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/recovery.sock` but review 061 rejected the old survey as a current veto. After eligibility checks, `/srv/st-557/run/harbor-relay/safe.sock` survived with bias 89. The configuration authority explicitly reconciled that a generic ENOENT elsewhere in the trace would not have supported this path.

Rollback evidence closed the Lantern Terminal case memorandum. The case memorandum confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 061 found no surviving temporary, backup, or journal file.

### Review 062 — North Quay, 2025-11-03

The North Quay path ledger separated namespace, purpose, ownership, and chronology. It observed EACCES without a supporting ownership transition. Snapshot `sealed-final` was authoritative, so `/run/harbor-relay/legacy.sock` from an earlier survey remained historical. Candidate `/srv/st-594/run/harbor-relay/recovery.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 108 was consulted last.

Case 062 entered the North Quay register when a loopback listener surviving package rollback. The catalog operations desk inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

### Review 063 — Beacon Inlet, 2026-04-10

Case 063 treated socket evidence as a time series. The final exact-path result was ENOENT followed later by EACCES, and the capture metadata designated `after` as the complete occupancy survey. Only `/srv/st-631/run/harbor-relay/quay.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/metrics.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 064 — West Lock, 2023-09-17

The West Lock path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/control.sock` from an earlier survey remained historical. Candidate `/srv/st-668/run/harbor-relay/data.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 76 was consulted last.

Case 064 entered the West Lock register when an incomplete lsof survey marked as current. The local transport group inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

### Review 065 — Copper Sound, 2024-02-24

Case 065 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-705/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 066 — Morrow Anchorage, 2025-07-04

Within the Morrow Anchorage review, lsof chronology mattered more than process names. The sealed `after` block did not contain `/srv/st-742/run/harbor-relay/recovery.sock`, although an old block still listed `/run/harbor-relay/legacy.sock`. Strace contained ENOENT followed later by EACCES; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 067 — Osprey Roads, 2026-12-11

The Osprey Roads socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 067 did not let the old entry veto current evidence. The eligible set then contained `/srv/st-779/run/harbor-relay/quay.sock` survived with bias 63. The publication control board explicitly adjudicated that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 068 — Heron Gate, 2023-05-18

The Heron Gate path ledger separated namespace, purpose, ownership, and chronology. It observed EACCES without a supporting ownership transition. Snapshot `sealed-final` was authoritative, so `/run/harbor-relay/control.sock` from an earlier survey remained historical. Candidate `/srv/st-816/run/harbor-relay/data.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 82 was consulted last.

The Heron Gate decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 82, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 069 — Marsh Berth, 2024-10-25

The Marsh Berth socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/recovery.sock` but review 069 rejected the old survey as a current veto. After eligibility checks, `/srv/st-853/run/harbor-relay/safe.sock` survived with bias 101. The service continuity group explicitly reviewed that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 070 — Ash Pier, 2025-03-05

The Ash Pier socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 070 preserved the old entry without granting it precedence; the filtered set left `/srv/st-890/run/harbor-relay/recovery.sock` survived with bias 50. The on-call review cell explicitly cross-checked that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 071 — Raven Basin, 2026-08-12

Within the Raven Basin review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-927/run/harbor-relay/quay.sock`, although an old block still listed `/run/harbor-relay/metrics.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

Rollback evidence closed the Raven Basin handoff memorandum. The handoff memorandum confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 071 verified cleanup of every temporary, backup, and journal name.

### Review 072 — Signal Jetty, 2023-01-19

The Signal Jetty path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/control.sock` from an earlier survey remained historical. Candidate `/srv/st-964/run/harbor-relay/data.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 88 was consulted last.

The Signal Jetty decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 88, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 073 — Slate Dock, 2024-06-26

Case 073 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-101/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

Rollback evidence closed the Slate Dock adjudication record. The adjudication record confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 073 left no `.tmp`, `.bak`, or journal artifact behind.

### Review 074 — Juniper Wharf, 2025-11-06

Case 074 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-138/run/harbor-relay/recovery.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/legacy.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 075 — Ferry Cut, 2026-04-13

The Ferry Cut path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/metrics.sock` from an earlier survey remained historical. Candidate `/srv/st-175/run/harbor-relay/quay.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 75 was consulted last.

### Review 076 — Tern Basin, 2023-09-20

The Tern Basin incident record begins when the quay systems committee at Tern Basin investigated an EACCES result misread as evidence for a new socket. The initial console transcript made the highest visible rank look reasonable, but the sealed request set and catalog recovery epoch did not support that shortcut. The catalog governance team traced the case because the same visible symptom had appeared in three earlier exercises with different authority sources.

Case 076 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-212/run/harbor-relay/data.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/control.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 077 — Storm Quay, 2024-02-27

Case 077 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-249/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

Rollback evidence closed the Storm Quay adjudication record. The adjudication record confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 077 found no surviving temporary, backup, or journal file.

### Review 078 — Cinder Wharf, 2025-07-07

The Cinder Wharf socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 078 preserved the old entry without granting it precedence; the filtered set left `/srv/st-286/run/harbor-relay/recovery.sock` survived with bias 62. The commissioning board explicitly preserved that a generic ENOENT elsewhere in the trace would not have supported this path.

Rollback evidence closed the Cinder Wharf review packet. The review packet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 078 left the publication directories free of implementation residue.

### Review 079 — Dunlin Reach, 2026-12-14

The Dunlin Reach socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 079 treated the earlier observation as non-authoritative. Current policy filters left `/srv/st-323/run/harbor-relay/quay.sock` survived with bias 81. The service continuity group explicitly reviewed that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 080 — Glass Harbor, 2023-05-21

Case 080 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-360/run/harbor-relay/data.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/control.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

The Glass Harbor decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 100, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 081 — Lantern Terminal, 2024-10-01

Case 081 treated socket evidence as a time series. The final exact-path result was ENOENT followed later by EACCES, and the capture metadata designated `after` as the complete occupancy survey. Only `/srv/st-397/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

Rollback evidence closed the Lantern Terminal case memorandum. The case memorandum confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 081 left no `.tmp`, `.bak`, or journal artifact behind.

### Review 082 — North Quay, 2025-03-08

Case 082 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-434/run/harbor-relay/recovery.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/legacy.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

The catalog operations desk logged review 082 for North Quay following a loopback listener surviving package rollback. Its draft configuration had copied the highest visible rank, which would have passed a single-request smoke test while violating the sealed commissioning authority model. The adjudication therefore reconstructed each source boundary before considering any candidate value.

### Review 083 — Beacon Inlet, 2026-08-15

The Beacon Inlet socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 083 did not let the old entry veto current evidence. The eligible set then contained `/srv/st-471/run/harbor-relay/quay.sock` survived with bias 87. The relay assurance committee explicitly verified that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 084 — West Lock, 2023-01-22

At West Lock, case 084 was opened by the local transport group after an incomplete lsof survey marked as current. A hurried operator had copied the highest visible rank; the result looked internally consistent until the request roles were compared as one set. Reviewers reopened identity, chronology, and publication evidence instead of editing the first obviously wrong value.

Within the West Lock review, lsof chronology mattered more than process names. The sealed `after` block did not contain `/srv/st-508/run/harbor-relay/data.sock`, although an old block still listed `/run/harbor-relay/control.sock`. Strace contained ENOENT followed later by EACCES; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

The West Lock decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 106, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 085 — Copper Sound, 2024-06-02

Case 085 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-545/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 086 — Morrow Anchorage, 2025-11-09

The Morrow Anchorage path ledger separated namespace, purpose, ownership, and chronology. It observed EACCES without a supporting ownership transition. Snapshot `sealed-final` was authoritative, so `/run/harbor-relay/legacy.sock` from an earlier survey remained historical. Candidate `/srv/st-582/run/harbor-relay/recovery.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 74 was consulted last.

Rollback evidence closed the Morrow Anchorage handoff memorandum. The handoff memorandum confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 086 left the publication directories free of implementation residue.

### Review 087 — Osprey Roads, 2026-04-16

The Osprey Roads socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 087 treated the earlier observation as non-authoritative. Current policy filters left `/srv/st-619/run/harbor-relay/quay.sock` survived with bias 93. The publication control board explicitly adjudicated that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 088 — Heron Gate, 2023-09-23

Case 088 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-656/run/harbor-relay/data.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/control.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 089 — Marsh Berth, 2024-02-03

Within the Marsh Berth review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-693/run/harbor-relay/safe.sock`, although an old block still listed `/run/harbor-relay/recovery.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 090 — Ash Pier, 2025-07-10

The Ash Pier path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/legacy.sock` from an earlier survey remained historical. Candidate `/srv/st-730/run/harbor-relay/recovery.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 80 was consulted last.

### Review 091 — Raven Basin, 2026-12-17

The Raven Basin socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 091 did not let the old entry veto current evidence. The eligible set then contained `/srv/st-767/run/harbor-relay/quay.sock` survived with bias 99. The configuration authority explicitly reconciled that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 092 — Signal Jetty, 2023-05-24

Case 092 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-804/run/harbor-relay/data.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/control.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

The Signal Jetty decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 118, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 093 — Slate Dock, 2024-10-04

The Slate Dock socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/recovery.sock` but review 093 rejected the old survey as a current veto. After eligibility checks, `/srv/st-841/run/harbor-relay/safe.sock` survived with bias 67. The relay assurance committee explicitly verified that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 094 — Juniper Wharf, 2025-03-11

Within the Juniper Wharf review, lsof chronology mattered more than process names. The sealed `current` block did not contain `/srv/st-878/run/harbor-relay/recovery.sock`, although an old block still listed `/run/harbor-relay/legacy.sock`. Strace contained a successful bind in the authoritative window; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 095 — Ferry Cut, 2026-08-18

The Ferry Cut socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 095 treated the earlier observation as non-authoritative. Current policy filters left `/srv/st-915/run/harbor-relay/quay.sock` survived with bias 105. The operations council explicitly documented that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 096 — Tern Basin, 2023-01-25

The Tern Basin path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/control.sock` from an earlier survey remained historical. Candidate `/srv/st-952/run/harbor-relay/data.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 54 was consulted last.

The Tern Basin working record concerns an EACCES result misread as evidence for a new socket at Tern Basin. The quay systems committee found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

The Tern Basin decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 54, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 097 — Storm Quay, 2024-06-05

The Storm Quay path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/recovery.sock` from an earlier survey remained historical. Candidate `/srv/st-989/run/harbor-relay/safe.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 73 was consulted last.

### Review 098 — Cinder Wharf, 2025-11-12

The Cinder Wharf socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 098 kept that entry as context only. Policy and interval checks then left `/srv/st-126/run/harbor-relay/recovery.sock` as the survivor with bias 92. The commissioning board explicitly preserved that a generic ENOENT elsewhere in the trace would not have supported this path.

Rollback evidence closed the Cinder Wharf review packet. The review packet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 098 finished without temporary, backup, or journal residue.

### Review 099 — Dunlin Reach, 2026-04-19

Within the Dunlin Reach review, lsof chronology mattered more than process names. The sealed `after` block did not contain `/srv/st-163/run/harbor-relay/quay.sock`, although an old block still listed `/run/harbor-relay/metrics.sock`. Strace contained ENOENT followed later by EACCES; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 100 — Glass Harbor, 2023-09-26

The Glass Harbor path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/control.sock` from an earlier survey remained historical. Candidate `/srv/st-200/run/harbor-relay/data.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 60 was consulted last.

Rollback evidence closed the Glass Harbor review packet. The review packet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 100 closed with clean publication directories and no publication residue.

### Review 101 — Lantern Terminal, 2024-02-06

The Lantern Terminal path ledger separated namespace, purpose, ownership, and chronology. It observed EACCES without a supporting ownership transition. Snapshot `sealed-final` was authoritative, so `/run/harbor-relay/recovery.sock` from an earlier survey remained historical. Candidate `/srv/st-237/run/harbor-relay/safe.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 79 was consulted last.

### Review 102 — North Quay, 2025-07-13

Within the North Quay review, lsof chronology mattered more than process names. The sealed `after` block did not contain `/srv/st-274/run/harbor-relay/recovery.sock`, although an old block still listed `/run/harbor-relay/legacy.sock`. Strace contained ENOENT followed later by EACCES; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

Rollback evidence closed the North Quay working record. The working record confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 102 left the publication directories free of implementation residue.

Case 102 entered the North Quay register when a loopback listener surviving package rollback. The catalog operations desk inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

### Review 103 — Beacon Inlet, 2026-12-20

Within the Beacon Inlet review, lsof chronology mattered more than process names. The sealed `current` block did not contain `/srv/st-311/run/harbor-relay/quay.sock`, although an old block still listed `/run/harbor-relay/metrics.sock`. Strace contained a successful bind in the authoritative window; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

Rollback evidence closed the Beacon Inlet commissioning worksheet. The commissioning worksheet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 103 verified cleanup of every temporary, backup, and journal name.

### Review 104 — West Lock, 2023-05-27

The local transport group logged review 104 for West Lock following an incomplete lsof survey marked as current. Its draft configuration had copied the highest visible rank, which would have passed a single-request smoke test while violating the sealed commissioning authority model. The adjudication therefore reconstructed each source boundary before considering any candidate value.

The West Lock socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/control.sock` but review 104 excluded the older entry from veto power; interval and policy checks left `/srv/st-348/run/harbor-relay/data.sock` survived with bias 66. The harbor systems panel explicitly examined that a generic ENOENT elsewhere in the trace would not have supported this path.

The West Lock decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 66, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 105 — Copper Sound, 2024-10-07

The Copper Sound path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/recovery.sock` from an earlier survey remained historical. Candidate `/srv/st-385/run/harbor-relay/safe.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 85 was consulted last.

Rollback evidence closed the Copper Sound commissioning worksheet. The commissioning worksheet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 105 left no `.tmp`, `.bak`, or journal artifact behind.

### Review 106 — Morrow Anchorage, 2025-03-14

The Morrow Anchorage path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/legacy.sock` from an earlier survey remained historical. Candidate `/srv/st-422/run/harbor-relay/recovery.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 104 was consulted last.

Rollback evidence closed the Morrow Anchorage handoff memorandum. The handoff memorandum confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 106 finished without temporary, backup, or journal residue.

### Review 107 — Osprey Roads, 2026-08-21

The Osprey Roads socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 107 did not let the old entry veto current evidence. The eligible set then contained `/srv/st-459/run/harbor-relay/quay.sock` survived with bias 53. The publication control board explicitly adjudicated that a generic ENOENT elsewhere in the trace would not have supported this path.

Rollback evidence closed the Osprey Roads commissioning worksheet. The commissioning worksheet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 107 confirmed that staging and rollback names were absent at exit.

### Review 108 — Heron Gate, 2023-01-01

The Heron Gate socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/control.sock` but review 108 used that entry as history rather than authority; applying current filters left `/srv/st-496/run/harbor-relay/data.sock` survived with bias 72. The commissioning board explicitly preserved that a generic ENOENT elsewhere in the trace would not have supported this path.

The Heron Gate decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 72, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 109 — Marsh Berth, 2024-06-08

Within the Marsh Berth review, lsof chronology mattered more than process names. The sealed `current` block did not contain `/srv/st-533/run/harbor-relay/safe.sock`, although an old block still listed `/run/harbor-relay/recovery.sock`. Strace contained a successful bind in the authoritative window; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

Rollback evidence closed the Marsh Berth handoff memorandum. The handoff memorandum confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 109 found no surviving temporary, backup, or journal file.

### Review 110 — Ash Pier, 2025-11-15

Within the Ash Pier review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-570/run/harbor-relay/recovery.sock`, although an old block still listed `/run/harbor-relay/legacy.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 111 — Raven Basin, 2026-04-22

The Raven Basin socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 111 treated the earlier observation as non-authoritative. Current policy filters left `/srv/st-607/run/harbor-relay/quay.sock` survived with bias 59. The configuration authority explicitly reconciled that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 112 — Signal Jetty, 2023-09-02

Case 112 treated socket evidence as a time series. The final exact-path result was a successful bind in the authoritative window, and the capture metadata designated `current` as the complete occupancy survey. Only `/srv/st-644/run/harbor-relay/data.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/control.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 113 — Slate Dock, 2024-02-09

Within the Slate Dock review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-681/run/harbor-relay/safe.sock`, although an old block still listed `/run/harbor-relay/recovery.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 114 — Juniper Wharf, 2025-07-16

Within the Juniper Wharf review, lsof chronology mattered more than process names. The sealed `after` block did not contain `/srv/st-718/run/harbor-relay/recovery.sock`, although an old block still listed `/run/harbor-relay/legacy.sock`. Strace contained ENOENT followed later by EACCES; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 115 — Ferry Cut, 2026-12-23

The Ferry Cut socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 115 did not let the old entry veto current evidence. The eligible set then contained `/srv/st-755/run/harbor-relay/quay.sock` survived with bias 65. The operations council explicitly documented that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 116 — Tern Basin, 2023-05-03

The Tern Basin incident record begins when the quay systems committee at Tern Basin investigated an EACCES result misread as evidence for a new socket. The initial console transcript made the highest visible rank look reasonable, but the sealed request set and catalog recovery epoch did not support that shortcut. The catalog governance team traced the case because the same visible symptom had appeared in three earlier exercises with different authority sources.

Within the Tern Basin review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-792/run/harbor-relay/data.sock`, although an old block still listed `/run/harbor-relay/control.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

The Tern Basin decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 84, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 117 — Storm Quay, 2024-10-10

The Storm Quay path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/recovery.sock` from an earlier survey remained historical. Candidate `/srv/st-829/run/harbor-relay/safe.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 103 was consulted last.

### Review 118 — Cinder Wharf, 2025-03-17

The Cinder Wharf path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/legacy.sock` from an earlier survey remained historical. Candidate `/srv/st-866/run/harbor-relay/recovery.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 52 was consulted last.

### Review 119 — Dunlin Reach, 2026-08-24

Case 119 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-903/run/harbor-relay/quay.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/metrics.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

Rollback evidence closed the Dunlin Reach commissioning worksheet. The commissioning worksheet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 119 verified cleanup of every temporary, backup, and journal name.

### Review 120 — Glass Harbor, 2023-01-04

Case 120 treated socket evidence as a time series. The final exact-path result was ENOENT followed later by EACCES, and the capture metadata designated `after` as the complete occupancy survey. Only `/srv/st-940/run/harbor-relay/data.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/control.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

The Glass Harbor decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 90, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

Rollback evidence closed the Glass Harbor review packet. The review packet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 120 ended with only the allowed publication and lock files present.

### Review 121 — Lantern Terminal, 2024-06-11

The Lantern Terminal socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/recovery.sock` but review 121 classified that entry as historical, not a veto; after policy and interval filtering, `/srv/st-977/run/harbor-relay/safe.sock` survived with bias 109. The configuration authority explicitly reconciled that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 122 — North Quay, 2025-11-18

Case 122 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-114/run/harbor-relay/recovery.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/legacy.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

The catalog operations desk logged review 122 for North Quay following a loopback listener surviving package rollback. Its draft configuration had copied the highest visible rank, which would have passed a single-request smoke test while violating the sealed commissioning authority model. The adjudication therefore reconstructed each source boundary before considering any candidate value.

### Review 123 — Beacon Inlet, 2026-04-25

The Beacon Inlet socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 123 did not let the old entry veto current evidence. The eligible set then contained `/srv/st-151/run/harbor-relay/quay.sock` survived with bias 77. The relay assurance committee explicitly verified that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 124 — West Lock, 2023-09-05

The West Lock path ledger separated namespace, purpose, ownership, and chronology. It observed a successful bind in the authoritative window. Snapshot `current` was authoritative, so `/run/harbor-relay/control.sock` from an earlier survey remained historical. Candidate `/srv/st-188/run/harbor-relay/data.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 96 was consulted last.

At West Lock, case 124 was opened by the local transport group after an incomplete lsof survey marked as current. A hurried operator had copied the highest visible rank; the result looked internally consistent until the request roles were compared as one set. Reviewers reopened identity, chronology, and publication evidence instead of editing the first obviously wrong value.

### Review 125 — Copper Sound, 2024-02-12

Within the Copper Sound review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-225/run/harbor-relay/safe.sock`, although an old block still listed `/run/harbor-relay/recovery.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

### Review 126 — Morrow Anchorage, 2025-07-19

The Morrow Anchorage path ledger separated namespace, purpose, ownership, and chronology. It observed ENOENT followed later by EACCES. Snapshot `after` was authoritative, so `/run/harbor-relay/legacy.sock` from an earlier survey remained historical. Candidate `/srv/st-262/run/harbor-relay/recovery.sock` was selected only after its final matching syscall was ENOENT and no current listener occupied it; its bias 64 was consulted last.

### Review 127 — Osprey Roads, 2026-12-26

The Osprey Roads socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 127 treated the earlier observation as non-authoritative. Current policy filters left `/srv/st-299/run/harbor-relay/quay.sock` survived with bias 83. The publication control board explicitly adjudicated that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 128 — Heron Gate, 2023-05-06

Within the Heron Gate review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-336/run/harbor-relay/data.sock`, although an old block still listed `/run/harbor-relay/control.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

The Heron Gate decision ledger recorded the selected family `K9A`, cohort `BLUE`, socket bias 102, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 129 — Marsh Berth, 2024-10-13

The Marsh Berth socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/recovery.sock` but review 129 classified that entry as historical, not a veto; after policy and interval filtering, `/srv/st-373/run/harbor-relay/safe.sock` survived with bias 51. The service continuity group explicitly reviewed that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 130 — Ash Pier, 2025-03-20

The Ash Pier socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 130 kept that entry as context only. Policy and interval checks then left `/srv/st-410/run/harbor-relay/recovery.sock` as the survivor with bias 70. The on-call review cell explicitly cross-checked that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 131 — Raven Basin, 2026-08-27

Case 131 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-447/run/harbor-relay/quay.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/metrics.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 132 — Signal Jetty, 2023-01-07

The Signal Jetty socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/control.sock` but review 132 used that entry as history rather than authority; applying current filters left `/srv/st-484/run/harbor-relay/data.sock` survived with bias 108. The evidence panel explicitly recorded that a generic ENOENT elsewhere in the trace would not have supported this path.

The Signal Jetty decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 108, and outcome 'rejected the attractive high-rank row'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

### Review 133 — Slate Dock, 2024-06-14

The Slate Dock socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/recovery.sock` but review 133 rejected the old survey as a current veto. After eligibility checks, `/srv/st-521/run/harbor-relay/safe.sock` survived with bias 57. The relay assurance committee explicitly verified that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 134 — Juniper Wharf, 2025-11-21

The Juniper Wharf socket analysis ordered exact-path outcomes and found EACCES without a supporting ownership transition. The latest complete lsof snapshot was `sealed-final`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 134 preserved the old entry without granting it precedence; the filtered set left `/srv/st-558/run/harbor-relay/recovery.sock` survived with bias 76. The harbor systems panel explicitly examined that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 135 — Ferry Cut, 2026-04-01

The Ferry Cut socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/metrics.sock` but review 135 treated the earlier observation as non-authoritative. Current policy filters left `/srv/st-595/run/harbor-relay/quay.sock` survived with bias 95. The operations council explicitly documented that a generic ENOENT elsewhere in the trace would not have supported this path.

Rollback evidence closed the Ferry Cut control note. The control note confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 135 verified cleanup of every temporary, backup, and journal name.

### Review 136 — Tern Basin, 2023-09-08

Case 136 entered the Tern Basin register when an EACCES result misread as evidence for a new socket. The quay systems committee inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

The Tern Basin socket analysis ordered exact-path outcomes and found a successful bind in the authoritative window. The latest complete lsof snapshot was `current`; an older survey mentioned `/run/harbor-relay/control.sock` but review 136 excluded the older entry from veto power; interval and policy checks left `/srv/st-632/run/harbor-relay/data.sock` survived with bias 114. The catalog governance team explicitly traced that a generic ENOENT elsewhere in the trace would not have supported this path.

Rollback evidence closed the Tern Basin working record. The working record confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 136 ended with only the allowed publication and lock files present.

### Review 137 — Storm Quay, 2024-02-15

Case 137 treated socket evidence as a time series. The final exact-path result was EACCES without a supporting ownership transition, and the capture metadata designated `sealed-final` as the complete occupancy survey. Only `/srv/st-669/run/harbor-relay/safe.sock` remained policy-compatible and absent. A stale `/run/harbor-relay/recovery.sock` listener was preserved in the incident narrative so future operators would not flatten the snapshots.

### Review 138 — Cinder Wharf, 2025-07-22

The Cinder Wharf socket analysis ordered exact-path outcomes and found ENOENT followed later by EACCES. The latest complete lsof snapshot was `after`; an older survey mentioned `/run/harbor-relay/legacy.sock` but review 138 kept that entry as context only. Policy and interval checks then left `/srv/st-706/run/harbor-relay/recovery.sock` as the survivor with bias 82. The commissioning board explicitly preserved that a generic ENOENT elsewhere in the trace would not have supported this path.

### Review 139 — Dunlin Reach, 2026-12-02

Within the Dunlin Reach review, lsof chronology mattered more than process names. The sealed `current` block did not contain `/srv/st-743/run/harbor-relay/quay.sock`, although an old block still listed `/run/harbor-relay/metrics.sock`. Strace contained a successful bind in the authoritative window; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

Rollback evidence closed the Dunlin Reach commissioning worksheet. The commissioning worksheet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 139 confirmed that staging and rollback names were absent at exit.

### Review 140 — Glass Harbor, 2023-05-09

Within the Glass Harbor review, lsof chronology mattered more than process names. The sealed `sealed-final` block did not contain `/srv/st-780/run/harbor-relay/data.sock`, although an old block still listed `/run/harbor-relay/control.sock`. Strace contained EACCES without a supporting ownership transition; the panel rejected every candidate whose last exact-path event was permission or collision evidence, then compared the remaining bias values.

The Glass Harbor decision ledger recorded the selected family `R7`, cohort `BLUE`, socket bias 50, and outcome 'used the zero-digest convention for recursive artifacts'. The ledger also preserved the rejected shortcut 'copied the highest visible rank' as negative evidence, because omitting rejected alternatives had previously made an audit appear deterministic when it was merely incomplete.

Rollback evidence closed the Glass Harbor review packet. The review packet confirms that the commissioning procedure backed up existing regular files only after staging and relay validation, then restored them if a later rename failed. Audit decisions explained identity, socket rejection, route directives, arithmetic, and staged validation. Review 140 closed with clean publication directories and no publication residue.


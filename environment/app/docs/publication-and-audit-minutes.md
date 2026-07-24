# Publication and Audit Board Minutes

Revision HRH-2026.07-R11

These minutes define service-generation staging and publication, the lock boundary, destination-local staging, relay validation, rollback, deterministic identity, audit reconciliation, and the zero-digest convention for recursive artifacts. The board records include failed publication rehearsals because transactional correctness is demonstrated by preservation of the previous generation, not merely by one successful rename sequence.

## Policy chapter 10: Service publication and commissioning

Commissioning acquires the root-scoped advisory lock before catalog invocation. Staging is destination-local. The prior publication is captured before replacement. If any later replacement, chmod, audit creation, manifest creation, or staged relay validation fails, every prior file is restored and newly introduced outputs are removed. A successful publication leaves the required empty `/app/var/harbor-deployment.lock` at mode `0600`, exact modes on the five generation files, no staging residue, and audit rows that describe the bytes on disk. Throughout these minutes, "no residue" excludes the required persistent lock and means no temporary, backup, SQLite journal/WAL/SHM, compiler, or build artifacts. Re-running unchanged evidence is content-idempotent, including the SQLite file.

## Policy chapter 11: Audit interpretation

The audit database is a current-state proof. input_artifact rows show what was read, decision rows explain material selection and rejection points, assertions correspond to the catalog audit rules, and publication_file binds expected bytes to final paths. The manifest self-entry uses the zero-digest convention described by the publication contract. An audit with all assertions set to one is still invalid if its configuration, route, or publication rows disagree with files.

## Review archive

The records are ordered by review number, not by precedence. Current commissioning inputs remain controlling. Cross-references with the same review number in companion volumes describe another domain of the same event.

### Review 002 — North Quay, 2025-11-15

The closing reconciliation for review 002 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 002, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 003 — Beacon Inlet, 2026-04-22

Publication review 003 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 004 — West Lock, 2023-09-02

Planning evidence in the West Lock incident file computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 005 — Copper Sound, 2024-02-09

The closing reconciliation for review 005 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 005, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 006 — Morrow Anchorage, 2025-07-16

Planning evidence in the Morrow Anchorage handoff memorandum computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 008 — Heron Gate, 2023-05-03

The closing reconciliation for review 008 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 008, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 009 — Marsh Berth, 2024-10-10

The closing reconciliation for review 009 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 009, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 013 — Slate Dock, 2024-06-11

The request bundle in case 013 used `slate-dock-5`, not a raw site key. Temporal alias adjudication reached `st-581` because 2024-06-01T00:00:00Z fell inside the selected row's closed interval. The publication control board rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `WARM-PIER`.

Publication review 013 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 014 — Juniper Wharf, 2025-11-18

Case 014 entered the Juniper Wharf register after a late failure left mixed publication generations. The local transport group inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

The closing reconciliation for review 014 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 014, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 016 — Tern Basin, 2023-09-05

Planning evidence in the Tern Basin working record computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 017 — Storm Quay, 2024-02-12

Publication review 017 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 018 — Cinder Wharf, 2025-07-19

Planning evidence in the Cinder Wharf review packet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 019 — Dunlin Reach, 2026-12-26

Planning evidence in the Dunlin Reach commissioning worksheet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 020 — Glass Harbor, 2023-05-06

Publication review 020 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 021 — Lantern Terminal, 2024-10-13

Publication review 021 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 022 — North Quay, 2025-03-20

Planning evidence in the North Quay working record computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 023 — Beacon Inlet, 2026-08-27

The closing reconciliation for review 023 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 023, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 024 — West Lock, 2023-01-07

The West Lock record demonstrates that a filesystem path cannot establish site identity. Alias `west-lock-7` resolved to `st-988` only after the enabled contexts were filtered at generation 86. The three request roles agreed on `COLD-QUAY` and `custody`; the common headers were supporting evidence, not an authority substitute, in review 024.

Publication review 024 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 026 — Morrow Anchorage, 2025-11-21

Publication review 026 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 027 — Osprey Roads, 2026-04-01

Publication review 027 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 028 — Heron Gate, 2023-09-08

Planning evidence in the Heron Gate working record computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 029 — Marsh Berth, 2024-02-15

Publication review 029 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 030 — Ash Pier, 2025-07-22

The closing reconciliation for review 030 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 030, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 031 — Raven Basin, 2026-12-02

Planning evidence in the Raven Basin handoff memorandum computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 032 — Signal Jetty, 2023-05-09

Planning evidence in the Signal Jetty review packet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 033 — Slate Dock, 2024-10-16

Publication review 033 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 034 — Juniper Wharf, 2025-03-23

The local transport group logged review 034 for Juniper Wharf following a late failure leaving mixed publication generations. Its draft configuration had copied the highest visible rank, which would have passed a single-request smoke test while violating the sealed commissioning authority model. The adjudication therefore reconstructed each source boundary before considering any candidate value.

Planning evidence in the Juniper Wharf shift dossier computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 036 — Tern Basin, 2023-01-10

Publication review 036 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 037 — Storm Quay, 2024-06-17

Publication review 037 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 038 — Cinder Wharf, 2025-11-24

Publication review 038 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 039 — Dunlin Reach, 2026-04-04

Planning evidence in the Dunlin Reach commissioning worksheet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 041 — Lantern Terminal, 2024-02-18

Planning evidence in the Lantern Terminal case memorandum computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 042 — North Quay, 2025-07-25

The closing reconciliation for review 042 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 042, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 043 — Beacon Inlet, 2026-12-05

The closing reconciliation for review 043 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 043, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 044 — West Lock, 2023-05-12

The West Lock identity review compared alias `west-lock-9` across closed intervals. The winning row became effective on 2023-05-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 044 required catalog-backed alias authority even for a literal-looking key. Every request role carried segment `DELTA` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 045 — Copper Sound, 2024-10-19

Planning evidence in the Copper Sound commissioning worksheet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 046 — Morrow Anchorage, 2025-03-26

Planning evidence in the Morrow Anchorage handoff memorandum computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 047 — Osprey Roads, 2026-08-06

Planning evidence in the Osprey Roads commissioning worksheet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 049 — Marsh Berth, 2024-06-20

Publication review 049 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 050 — Ash Pier, 2025-11-27

The closing reconciliation for review 050 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 050, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 051 — Raven Basin, 2026-04-07

Publication review 051 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 052 — Signal Jetty, 2023-09-14

At Signal Jetty, case 052 was opened by the catalog operations desk after a disabled adjustment treated as current. A hurried operator had copied the highest visible rank; the result looked internally consistent until the request roles were compared as one set. Reviewers reopened identity, chronology, and publication evidence instead of editing the first obviously wrong value.

### Review 053 — Slate Dock, 2024-02-21

The request bundle in case 053 used `slate-dock-9`, not a raw site key. Temporal alias adjudication reached `st-261` because 2024-02-01T00:00:00Z fell inside the selected row's closed interval. The publication control board rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `TIDAL-GATE`.

The closing reconciliation for review 053 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 053, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 054 — Juniper Wharf, 2025-07-01

Case 054 entered the Juniper Wharf register after a late failure left mixed publication generations. The local transport group inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

The closing reconciliation for review 054 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 054, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 056 — Tern Basin, 2023-05-15

Publication review 056 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 057 — Storm Quay, 2024-10-22

Publication review 057 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 059 — Dunlin Reach, 2026-08-09

The closing reconciliation for review 059 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 059, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 060 — Glass Harbor, 2023-01-16

Publication review 060 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 062 — North Quay, 2025-11-03

The closing reconciliation for review 062 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 062, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 063 — Beacon Inlet, 2026-04-10

The request bundle in case 063 used `beacon-inlet-1`, not a raw site key. Temporal alias adjudication reached `st-631` because 2026-04-01T00:00:00Z fell inside the selected row's closed interval. The publication control board rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `NIGHT-BERTH`.

The closing reconciliation for review 063 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 063, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 064 — West Lock, 2023-09-17

The West Lock identity review compared alias `west-lock-2` across closed intervals. The winning row became effective on 2023-09-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 064 required the same alias proof for literal and nonliteral values. Every request role carried segment `DRY-DOCK` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

The closing reconciliation for review 064 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 064, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 065 — Copper Sound, 2024-02-24

Planning evidence in the Copper Sound commissioning worksheet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 066 — Morrow Anchorage, 2025-07-04

The closing reconciliation for review 066 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 066, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 067 — Osprey Roads, 2026-12-11

The closing reconciliation for review 067 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 067, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 068 — Heron Gate, 2023-05-18

Publication review 068 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 069 — Marsh Berth, 2024-10-25

Planning evidence in the Marsh Berth handoff memorandum computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 070 — Ash Pier, 2025-03-05

The closing reconciliation for review 070 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 070, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 072 — Signal Jetty, 2023-01-19

At Signal Jetty, case 072 was opened by the catalog operations desk after a disabled adjustment treated as current. A hurried operator had copied the highest visible rank; the result looked internally consistent until the request roles were compared as one set. Reviewers reopened identity, chronology, and publication evidence instead of editing the first obviously wrong value.

The closing reconciliation for review 072 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 072, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 073 — Slate Dock, 2024-06-26

The request bundle in case 073 used `slate-dock-2`, not a raw site key. Temporal alias adjudication reached `st-101` because 2024-06-01T00:00:00Z fell inside the selected row's closed interval. The publication control board rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `WARM-PIER`.

### Review 074 — Juniper Wharf, 2025-11-06

The Juniper Wharf incident record begins when the local transport group at Juniper Wharf investigated a late failure leaving mixed publication generations. The initial console transcript made the highest visible rank look reasonable, but the sealed request set and catalog recovery epoch did not support that shortcut. The service continuity group reviewed the case because the same visible symptom had appeared in three earlier exercises with different authority sources.

Publication review 074 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 075 — Ferry Cut, 2026-04-13

Publication review 075 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 076 — Tern Basin, 2023-09-20

Publication review 076 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 079 — Dunlin Reach, 2026-12-14

Planning evidence in the Dunlin Reach commissioning worksheet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 080 — Glass Harbor, 2023-05-21

Publication review 080 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 082 — North Quay, 2025-03-08

Publication review 082 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 083 — Beacon Inlet, 2026-08-15

Planning evidence in the Beacon Inlet commissioning worksheet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 084 — West Lock, 2023-01-22

Publication review 084 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 085 — Copper Sound, 2024-06-02

The closing reconciliation for review 085 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 085, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 087 — Osprey Roads, 2026-04-16

Planning evidence in the Osprey Roads commissioning worksheet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 088 — Heron Gate, 2023-09-23

Planning evidence in the Heron Gate working record computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 089 — Marsh Berth, 2024-02-03

Publication review 089 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 090 — Ash Pier, 2025-07-10

Publication review 090 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 091 — Raven Basin, 2026-12-17

Planning evidence in the Raven Basin handoff memorandum computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 092 — Signal Jetty, 2023-05-24

Publication review 092 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 093 — Slate Dock, 2024-10-04

Publication review 093 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 094 — Juniper Wharf, 2025-03-11

Case 094 entered the Juniper Wharf register after a late failure left mixed publication generations. The local transport group inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

Publication review 094 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 095 — Ferry Cut, 2026-08-18

Planning evidence in the Ferry Cut control note computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 096 — Tern Basin, 2023-01-25

The closing reconciliation for review 096 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 096, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 097 — Storm Quay, 2024-06-05

The closing reconciliation for review 097 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 097, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 099 — Dunlin Reach, 2026-04-19

Publication review 099 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 101 — Lantern Terminal, 2024-02-06

Planning evidence in the Lantern Terminal case memorandum computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 104 — West Lock, 2023-05-27

Publication review 104 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 108 — Heron Gate, 2023-01-01

Planning evidence in the Heron Gate working record computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 110 — Ash Pier, 2025-11-15

The closing reconciliation for review 110 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 110, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 111 — Raven Basin, 2026-04-22

Planning evidence in the Raven Basin handoff memorandum computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 112 — Signal Jetty, 2023-09-02

Planning evidence in the Signal Jetty review packet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 113 — Slate Dock, 2024-02-09

The closing reconciliation for review 113 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 113, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 114 — Juniper Wharf, 2025-07-16

The local transport group logged review 114 for Juniper Wharf following a late failure leaving mixed publication generations. Its draft configuration had copied the highest visible rank, which would have passed a single-request smoke test while violating the sealed commissioning authority model. The adjudication therefore reconstructed each source boundary before considering any candidate value.

Publication review 114 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 115 — Ferry Cut, 2026-12-23

Planning evidence in the Ferry Cut control note computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 116 — Tern Basin, 2023-05-03

Planning evidence in the Tern Basin working record computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 117 — Storm Quay, 2024-10-10

Planning evidence in the Storm Quay adjudication record computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 118 — Cinder Wharf, 2025-03-17

Publication review 118 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 121 — Lantern Terminal, 2024-06-11

Planning evidence in the Lantern Terminal case memorandum computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 122 — North Quay, 2025-11-18

The closing reconciliation for review 122 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 122, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 123 — Beacon Inlet, 2026-04-25

Publication review 123 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 124 — West Lock, 2023-09-05

The West Lock identity review compared alias `west-lock-8` across closed intervals. The winning row became effective on 2023-09-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 124 required catalog-backed alias authority even for a literal-looking key. Every request role carried segment `DRY-DOCK` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

Publication review 124 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 125 — Copper Sound, 2024-02-12

Publication review 125 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 126 — Morrow Anchorage, 2025-07-19

Planning evidence in the Morrow Anchorage handoff memorandum computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 127 — Osprey Roads, 2026-12-26

Publication review 127 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 128 — Heron Gate, 2023-05-06

Publication review 128 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 129 — Marsh Berth, 2024-10-13

Publication review 129 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 130 — Ash Pier, 2025-03-20

The closing reconciliation for review 130 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 130, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 131 — Raven Basin, 2026-08-27

Publication review 131 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 132 — Signal Jetty, 2023-01-07

The closing reconciliation for review 132 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 132, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 133 — Slate Dock, 2024-06-14

Publication review 133 staged files beside their destinations, validated the staged relay map, and retained the previous generation until every candidate artifact existed. The simulated late failure restored prior bytes and modes. The applied audit contained one run, ordered decisions, passing assertions, and five publication rows. Recursive audit and manifest entries used the documented zero-digest and zero-byte convention.

### Review 134 — Juniper Wharf, 2025-11-21

At Juniper Wharf, case 134 was opened by the local transport group after a late failure leaving mixed publication generations. A hurried operator had copied the highest visible rank; the result looked internally consistent until the request roles were compared as one set. Reviewers reopened identity, chronology, and publication evidence instead of editing the first obviously wrong value.

Planning evidence in the Juniper Wharf shift dossier computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.

### Review 137 — Storm Quay, 2024-02-15

The closing reconciliation for review 137 compared stdout, publication JSON, SQLite rows, text bytes, and modes. Repetition over unchanged evidence produced the same 24-character run identity and byte-identical database. For review 137, validation failure preserved the old publication, and a held lock prevented catalog access.

### Review 138 — Cinder Wharf, 2025-07-22

Planning evidence in the Cinder Wharf review packet computed the same logical state without creating a root, lock, backup, or temporary file. Apply acquired the nonblocking root lock before the catalog call, validated destination-local stages, and replaced the generation only after all five artifacts were ready. A forced path error returned the publication class and left no residue.


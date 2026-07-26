# Route Governance and Closure Record

Revision HRH-2026.07-R11

This record contains the source-epoch, family, cohort, directive, replacement, withdrawal, requirement, and dependency rules used to construct a relay route map. Route selection is not a ranking query. It is a constrained graph transformation whose membership must stabilize before timeout, authorization, descriptor, or publication calculations are accepted. The review packets preserve rejected alternatives because a final map without provenance is not a defensible service deployment.

## Policy chapter 5: Route family resolution

A family rule matches the selected context and the request-set segment and replay mode. `*` matches one field and contributes no specificity; literal fields contribute to the stored specificity, which must equal the actual literal count or the row is malformed. Only enabled rows whose closed interval contains the recovery epoch are eligible. Compare candidates by specificity, then source_epoch, then precedence rank. A tie across different family codes after all three dimensions is ambiguous.

The current route cohort comes from deployment_context. Routes from other cohorts are never fallback candidates. Route effective intervals are closed. Candidate identity is retained because directives and dependencies address route IDs, not endpoint keys.

## Policy chapter 6: Candidate precedence, directives, and closure

Within a family and cohort, active base-class route candidates are grouped by method and external path. Replacement- and required-class rows do not enter initial selection. Later source_epoch outranks precedence_rank; precedence is consulted only when source epochs tie. A final tie between different route IDs is ambiguous.

Effective directives are applied in source_epoch, precedence_rank, directive_id order. Withdraw removes the named target if present and records the decision. Replace removes its target and installs the named replacement candidate, which must belong to the same site, family, and cohort and be active at the epoch. Require installs the named candidate if it is otherwise eligible. Two effective directives at the same ordering dimensions that demand incompatible outcomes for one target invalidate the catalog.

After directives, dependencies are closed transitively. Every required route must be eligible in the same family and cohort. Dependency cycles are allowed only when every member is already selected; a cycle that would have to synthesize an ineligible member fails. Deduplicate again after closure using source-epoch precedence. The resulting map is sorted by method then path and must route every request in the replay set.

## Review archive

The records are ordered by review number, not by precedence. Current commissioning inputs remain controlling. Cross-references with the same review number in companion volumes describe another domain of the same event.

### Review 001 — Lantern Terminal, 2024-06-08

The Lantern Terminal route ledger resolved `K9B` for segment `WARM-PIER`. Review 001 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 1 replacement and 0 withdrawals directives changed membership; 2 required rows entered before transitive closure. Review 001 therefore published a map with 4 keys.

### Review 002 — North Quay, 2025-11-15

Route review 002 treated selection as a graph problem rather than a top-rank query. Family `M4` won for `DELTA`; cohort `BLUE` constrained candidate compatibility. Directives contributed 2 replacements, 0 withdrawals, and 1 requirement. Review 002 stabilized dependency closure before final deduplication, leaving 5 routes.

### Review 003 — Beacon Inlet, 2026-04-22

Route review 003 treated selection as a graph problem rather than a top-rank query. Family `S2` won for `NIGHT-BERTH`; cohort `SILVER` constrained candidate compatibility. Directives contributed 0 replacements, 1 withdrawal, and 2 requirements. Review 003 stabilized dependency closure before final deduplication, leaving 6 routes.

### Review 004 — West Lock, 2023-09-02

The West Lock route ledger resolved `R7` for segment `DRY-DOCK`. Review 004 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 1 replacement and 1 withdrawal directives changed membership; 1 required row entered before transitive closure. Review 004 therefore published a map with 7 keys.

### Review 005 — Copper Sound, 2024-02-09

Route review 005 treated selection as a graph problem rather than a top-rank query. Family `F7` won for `TIDAL-GATE`; cohort `SILVER` constrained candidate compatibility. Directives contributed 2 replacements, 1 withdrawal, and 2 requirements. Review 005 stabilized dependency closure before final deduplication, leaving 3 routes.

### Review 006 — Morrow Anchorage, 2025-07-16

The Morrow Anchorage handoff memorandum concerns a cohort copied from a neighboring site at Morrow Anchorage. The quay systems committee found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

The Morrow Anchorage route ledger resolved `D3` for segment `COLD-QUAY`. Review 006 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 0 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 006 therefore published a map with 4 keys.

### Review 007 — Osprey Roads, 2026-12-23

Route review 007 treated selection as a graph problem rather than a top-rank query. Family `C8` won for `WARM-PIER`; cohort `SILVER` constrained candidate compatibility. Directives contributed 1 replacement, 0 withdrawals, and 2 requirements. Review 007 stabilized dependency closure before final deduplication, leaving 5 routes.

### Review 008 — Heron Gate, 2023-05-03

The Heron Gate incident record begins when the route governance board at Heron Gate investigated a catalog snapshot split across two generations. The initial console transcript made the highest visible rank look reasonable, but the sealed request set and catalog recovery epoch did not support that shortcut. The configuration authority documented the case because the same visible symptom had appeared in three earlier exercises with different authority sources.

Route review 008 treated selection as a graph problem rather than a top-rank query. Family `K9A` won for `DELTA`; cohort `BLUE` constrained candidate compatibility. Directives contributed 2 replacements, 0 withdrawals, and 1 requirement. Review 008 stabilized dependency closure before final deduplication, leaving 6 routes.

### Review 009 — Marsh Berth, 2024-10-10

The Marsh Berth route ledger resolved `K9B` for segment `NIGHT-BERTH`. Review 009 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 0 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 009 therefore published a map with 7 keys.

### Review 010 — Ash Pier, 2025-03-17

The Ash Pier route ledger resolved `M4` for segment `DRY-DOCK`. Review 010 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 1 replacement and 1 withdrawal directives changed membership; 1 required row entered before transitive closure. Review 010 therefore published a map with 3 keys.

### Review 012 — Signal Jetty, 2023-01-04

The Signal Jetty route ledger resolved `R7` for segment `COLD-QUAY`. Review 012 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 0 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 012 therefore published a map with 5 keys.

### Review 014 — Juniper Wharf, 2025-11-18

Route review 014 treated selection as a graph problem rather than a top-rank query. Family `D3` won for `DELTA`; cohort `BLUE` constrained candidate compatibility. Directives contributed 2 replacements, 0 withdrawals, and 1 requirement. Review 014 stabilized dependency closure before final deduplication, leaving 7 routes.

### Review 015 — Ferry Cut, 2026-04-25

Route review 015 treated selection as a graph problem rather than a top-rank query. Family `C8` won for `NIGHT-BERTH`; cohort `SILVER` constrained candidate compatibility. Directives contributed 0 replacements, 1 withdrawal, and 2 requirements. Review 015 stabilized dependency closure before final deduplication, leaving 3 routes.

### Review 016 — Tern Basin, 2023-09-05

Route review 016 treated selection as a graph problem rather than a top-rank query. Family `K9A` won for `DRY-DOCK`; cohort `BLUE` constrained candidate compatibility. Directives contributed 1 replacement, 1 withdrawal, and 1 requirement. Review 016 stabilized dependency closure before final deduplication, leaving 4 routes.

### Review 018 — Cinder Wharf, 2025-07-19

The Cinder Wharf review packet concerns a required route omitted because no sample called it at Cinder Wharf. The route governance board found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

### Review 019 — Dunlin Reach, 2026-12-26

Route review 019 treated selection as a graph problem rather than a top-rank query. Family `S2` won for `WARM-PIER`; cohort `SILVER` constrained candidate compatibility. Directives contributed 1 replacement, 0 withdrawals, and 2 requirements. Review 019 stabilized dependency closure before final deduplication, leaving 7 routes.

### Review 021 — Lantern Terminal, 2024-10-13

Case 021 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `F7` rather than a familiar fallback. Cohort `SILVER` excluded a newer but incompatible endpoint. After 0/1/2 replace-withdraw-require actions and dependency closure, 4 routes remained and every replay request had a key.

### Review 022 — North Quay, 2025-03-20

Route review 022 treated selection as a graph problem rather than a top-rank query. Family `D3` won for `DRY-DOCK`; cohort `BLUE` constrained candidate compatibility. Directives contributed 1 replacement, 1 withdrawal, and 1 requirement. Review 022 stabilized dependency closure before final deduplication, leaving 5 routes.

### Review 023 — Beacon Inlet, 2026-08-27

Route review 023 treated selection as a graph problem rather than a top-rank query. Family `C8` won for `TIDAL-GATE`; cohort `SILVER` constrained candidate compatibility. Directives contributed 2 replacements, 1 withdrawal, and 2 requirements. Review 023 stabilized dependency closure before final deduplication, leaving 6 routes.

### Review 025 — Copper Sound, 2024-06-14

The Copper Sound route ledger resolved `K9B` for segment `WARM-PIER`. Review 025 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 1 replacement and 0 withdrawals directives changed membership; 2 required rows entered before transitive closure. Review 025 therefore published a map with 3 keys.

### Review 026 — Morrow Anchorage, 2025-11-21

The Morrow Anchorage handoff memorandum concerns a cohort copied from a neighboring site at Morrow Anchorage. The quay systems committee found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

Route review 026 treated selection as a graph problem rather than a top-rank query. Family `M4` won for `DELTA`; cohort `BLUE` constrained candidate compatibility. Directives contributed 2 replacements, 0 withdrawals, and 1 requirement. Review 026 stabilized dependency closure before final deduplication, leaving 4 routes.

### Review 028 — Heron Gate, 2023-09-08

Case 028 entered the Heron Gate register when a catalog snapshot split across two generations. The route governance board inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

### Review 029 — Marsh Berth, 2024-02-15

Case 029 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `F7` rather than a familiar fallback. Cohort `SILVER` excluded a newer but incompatible endpoint. After 2/1/2 replace-withdraw-require actions and dependency closure, 7 routes remained and every replay request had a key.

### Review 030 — Ash Pier, 2025-07-22

Route review 030 treated selection as a graph problem rather than a top-rank query. Family `D3` won for `COLD-QUAY`; cohort `BLUE` constrained candidate compatibility. Directives contributed 0 replacements, 0 withdrawals, and 1 requirement. Review 030 stabilized dependency closure before final deduplication, leaving 3 routes.

### Review 032 — Signal Jetty, 2023-05-09

The Signal Jetty route ledger resolved `K9A` for segment `DELTA`. Review 032 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 2 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 032 therefore published a map with 5 keys.

### Review 033 — Slate Dock, 2024-10-16

Route review 033 treated selection as a graph problem rather than a top-rank query. Family `K9B` won for `NIGHT-BERTH`; cohort `SILVER` constrained candidate compatibility. Directives contributed 0 replacements, 1 withdrawal, and 2 requirements. Review 033 stabilized dependency closure before final deduplication, leaving 6 routes.

### Review 035 — Ferry Cut, 2026-08-03

Case 035 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `S2` rather than a familiar fallback. Cohort `SILVER` excluded a newer but incompatible endpoint. After 2/1/2 replace-withdraw-require actions and dependency closure, 3 routes remained and every replay request had a key.

### Review 036 — Tern Basin, 2023-01-10

Route review 036 treated selection as a graph problem rather than a top-rank query. Family `R7` won for `COLD-QUAY`; cohort `BLUE` constrained candidate compatibility. Directives contributed 0 replacements, 0 withdrawals, and 1 requirement. Review 036 stabilized dependency closure before final deduplication, leaving 4 routes.

### Review 037 — Storm Quay, 2024-06-17

Route review 037 treated selection as a graph problem rather than a top-rank query. Family `F7` won for `WARM-PIER`; cohort `SILVER` constrained candidate compatibility. Directives contributed 1 replacement, 0 withdrawals, and 2 requirements. Review 037 stabilized dependency closure before final deduplication, leaving 5 routes.

### Review 038 — Cinder Wharf, 2025-11-24

Case 038 entered the Cinder Wharf register when a required route omitted because no sample called it. The route governance board inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

Route review 038 treated selection as a graph problem rather than a top-rank query. Family `D3` won for `DELTA`; cohort `BLUE` constrained candidate compatibility. Directives contributed 2 replacements, 0 withdrawals, and 1 requirement. Review 038 stabilized dependency closure before final deduplication, leaving 6 routes.

### Review 039 — Dunlin Reach, 2026-04-04

The Dunlin Reach route ledger resolved `C8` for segment `NIGHT-BERTH`. Review 039 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 0 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 039 therefore published a map with 7 keys.

### Review 040 — Glass Harbor, 2023-09-11

Case 040 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `K9A` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 1/1/1 replace-withdraw-require actions and dependency closure, 3 routes remained and every replay request had a key.

### Review 041 — Lantern Terminal, 2024-02-18

The Lantern Terminal route ledger resolved `K9B` for segment `TIDAL-GATE`. Review 041 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 2 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 041 therefore published a map with 4 keys.

### Review 042 — North Quay, 2025-07-25

Case 042 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `M4` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 0/0/1 replace-withdraw-require actions and dependency closure, 5 routes remained and every replay request had a key.

### Review 043 — Beacon Inlet, 2026-12-05

Route review 043 treated selection as a graph problem rather than a top-rank query. Family `S2` won for `WARM-PIER`; cohort `SILVER` constrained candidate compatibility. Directives contributed 1 replacement, 0 withdrawals, and 2 requirements. Review 043 stabilized dependency closure before final deduplication, leaving 6 routes.

### Review 044 — West Lock, 2023-05-12

Case 044 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `R7` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 2/0/1 replace-withdraw-require actions and dependency closure, 7 routes remained and every replay request had a key.

### Review 045 — Copper Sound, 2024-10-19

The Copper Sound route ledger resolved `F7` for segment `NIGHT-BERTH`. Review 045 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 0 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 045 therefore published a map with 3 keys.

### Review 046 — Morrow Anchorage, 2025-03-26

The Morrow Anchorage route ledger resolved `D3` for segment `DRY-DOCK`. Review 046 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 1 replacement and 1 withdrawal directives changed membership; 1 required row entered before transitive closure. Review 046 therefore published a map with 4 keys.

At Morrow Anchorage, case 046 was opened by the quay systems committee after a cohort copied from a neighboring site. A hurried operator had copied the highest visible rank; the result looked internally consistent until the request roles were compared as one set. Reviewers reopened identity, chronology, and publication evidence instead of editing the first obviously wrong value.

### Review 047 — Osprey Roads, 2026-08-06

The Osprey Roads route ledger resolved `C8` for segment `TIDAL-GATE`. Review 047 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 2 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 047 therefore published a map with 5 keys.

### Review 048 — Heron Gate, 2023-01-13

The Heron Gate working record concerns a catalog snapshot split across two generations at Heron Gate. The route governance board found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

Case 048 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `K9A` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 0/0/1 replace-withdraw-require actions and dependency closure, 6 routes remained and every replay request had a key.

### Review 050 — Ash Pier, 2025-11-27

Route review 050 treated selection as a graph problem rather than a top-rank query. Family `M4` won for `DELTA`; cohort `BLUE` constrained candidate compatibility. Directives contributed 2 replacements, 0 withdrawals, and 1 requirement. Review 050 stabilized dependency closure before final deduplication, leaving 3 routes.

### Review 051 — Raven Basin, 2026-04-07

Route review 051 treated selection as a graph problem rather than a top-rank query. Family `S2` won for `NIGHT-BERTH`; cohort `SILVER` constrained candidate compatibility. Directives contributed 0 replacements, 1 withdrawal, and 2 requirements. Review 051 stabilized dependency closure before final deduplication, leaving 4 routes.

### Review 052 — Signal Jetty, 2023-09-14

Case 052 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `R7` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 1/1/1 replace-withdraw-require actions and dependency closure, 5 routes remained and every replay request had a key.

### Review 055 — Ferry Cut, 2026-12-08

The Ferry Cut route ledger resolved `C8` for segment `WARM-PIER`. Review 055 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 1 replacement and 0 withdrawals directives changed membership; 2 required rows entered before transitive closure. Review 055 therefore published a map with 3 keys.

### Review 056 — Tern Basin, 2023-05-15

The Tern Basin route ledger resolved `K9A` for segment `DELTA`. Review 056 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 2 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 056 therefore published a map with 4 keys.

### Review 057 — Storm Quay, 2024-10-22

Route review 057 treated selection as a graph problem rather than a top-rank query. Family `K9B` won for `NIGHT-BERTH`; cohort `SILVER` constrained candidate compatibility. Directives contributed 0 replacements, 1 withdrawal, and 2 requirements. Review 057 stabilized dependency closure before final deduplication, leaving 5 routes.

### Review 058 — Cinder Wharf, 2025-03-02

Route review 058 treated selection as a graph problem rather than a top-rank query. Family `M4` won for `DRY-DOCK`; cohort `BLUE` constrained candidate compatibility. Directives contributed 1 replacement, 1 withdrawal, and 1 requirement. Review 058 stabilized dependency closure before final deduplication, leaving 6 routes.

At Cinder Wharf, case 058 was opened by the route governance board after a required route omitted because no sample called it. A hurried operator had copied the highest visible rank; the result looked internally consistent until the request roles were compared as one set. Reviewers reopened identity, chronology, and publication evidence instead of editing the first obviously wrong value.

### Review 059 — Dunlin Reach, 2026-08-09

The Dunlin Reach route ledger resolved `S2` for segment `TIDAL-GATE`. Review 059 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 2 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 059 therefore published a map with 7 keys.

### Review 062 — North Quay, 2025-11-03

Case 062 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `D3` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 2/0/1 replace-withdraw-require actions and dependency closure, 5 routes remained and every replay request had a key.

### Review 066 — Morrow Anchorage, 2025-07-04

The Morrow Anchorage handoff memorandum concerns a cohort copied from a neighboring site at Morrow Anchorage. The quay systems committee found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

Route review 066 treated selection as a graph problem rather than a top-rank query. Family `M4` won for `COLD-QUAY`; cohort `BLUE` constrained candidate compatibility. Directives contributed 0 replacements, 0 withdrawals, and 1 requirement. Review 066 stabilized dependency closure before final deduplication, leaving 4 routes.

### Review 067 — Osprey Roads, 2026-12-11

The Osprey Roads route ledger resolved `S2` for segment `WARM-PIER`. Review 067 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 1 replacement and 0 withdrawals directives changed membership; 2 required rows entered before transitive closure. Review 067 therefore published a map with 5 keys.

### Review 068 — Heron Gate, 2023-05-18

The Heron Gate incident record begins when the route governance board at Heron Gate investigated a catalog snapshot split across two generations. The initial console transcript made the highest visible rank look reasonable, but the sealed request set and catalog recovery epoch did not support that shortcut. The configuration authority documented the case because the same visible symptom had appeared in three earlier exercises with different authority sources.

Case 068 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `R7` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 2/0/1 replace-withdraw-require actions and dependency closure, 6 routes remained and every replay request had a key.

### Review 071 — Raven Basin, 2026-08-12

The Raven Basin route ledger resolved `C8` for segment `TIDAL-GATE`. Review 071 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 2 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 071 therefore published a map with 4 keys.

### Review 073 — Slate Dock, 2024-06-26

Route review 073 treated selection as a graph problem rather than a top-rank query. Family `K9B` won for `WARM-PIER`; cohort `SILVER` constrained candidate compatibility. Directives contributed 1 replacement, 0 withdrawals, and 2 requirements. Review 073 stabilized dependency closure before final deduplication, leaving 6 routes.

### Review 074 — Juniper Wharf, 2025-11-06

The Juniper Wharf route ledger resolved `M4` for segment `DELTA`. Review 074 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 2 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 074 therefore published a map with 7 keys.

### Review 075 — Ferry Cut, 2026-04-13

Route review 075 treated selection as a graph problem rather than a top-rank query. Family `S2` won for `NIGHT-BERTH`; cohort `SILVER` constrained candidate compatibility. Directives contributed 0 replacements, 1 withdrawal, and 2 requirements. Review 075 stabilized dependency closure before final deduplication, leaving 3 routes.

### Review 077 — Storm Quay, 2024-02-27

Route review 077 treated selection as a graph problem rather than a top-rank query. Family `F7` won for `TIDAL-GATE`; cohort `SILVER` constrained candidate compatibility. Directives contributed 2 replacements, 1 withdrawal, and 2 requirements. Review 077 stabilized dependency closure before final deduplication, leaving 5 routes.

### Review 078 — Cinder Wharf, 2025-07-07

Case 078 entered the Cinder Wharf register when a required route omitted because no sample called it. The route governance board inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

The Cinder Wharf route ledger resolved `D3` for segment `COLD-QUAY`. Review 078 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 0 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 078 therefore published a map with 6 keys.

### Review 081 — Lantern Terminal, 2024-10-01

The Lantern Terminal route ledger resolved `K9B` for segment `NIGHT-BERTH`. Review 081 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 0 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 081 therefore published a map with 4 keys.

### Review 083 — Beacon Inlet, 2026-08-15

Case 083 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `S2` rather than a familiar fallback. Cohort `SILVER` excluded a newer but incompatible endpoint. After 2/1/2 replace-withdraw-require actions and dependency closure, 6 routes remained and every replay request had a key.

### Review 084 — West Lock, 2023-01-22

Case 084 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `R7` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 0/0/1 replace-withdraw-require actions and dependency closure, 7 routes remained and every replay request had a key.

### Review 086 — Morrow Anchorage, 2025-11-09

Case 086 entered the Morrow Anchorage register when a cohort copied from a neighboring site. The quay systems committee inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

Case 086 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `D3` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 2/0/1 replace-withdraw-require actions and dependency closure, 4 routes remained and every replay request had a key.

### Review 087 — Osprey Roads, 2026-04-16

The Osprey Roads route ledger resolved `C8` for segment `NIGHT-BERTH`. Review 087 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 0 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 087 therefore published a map with 5 keys.

### Review 088 — Heron Gate, 2023-09-23

The Heron Gate incident record begins when the route governance board at Heron Gate investigated a catalog snapshot split across two generations. The initial console transcript made the highest visible rank look reasonable, but the sealed request set and catalog recovery epoch did not support that shortcut. The configuration authority documented the case because the same visible symptom had appeared in three earlier exercises with different authority sources.

### Review 089 — Marsh Berth, 2024-02-03

Case 089 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `K9B` rather than a familiar fallback. Cohort `SILVER` excluded a newer but incompatible endpoint. After 2/1/2 replace-withdraw-require actions and dependency closure, 7 routes remained and every replay request had a key.

### Review 090 — Ash Pier, 2025-07-10

The Ash Pier route ledger resolved `M4` for segment `COLD-QUAY`. Review 090 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 0 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 090 therefore published a map with 3 keys.

### Review 092 — Signal Jetty, 2023-05-24

The Signal Jetty route ledger resolved `R7` for segment `DELTA`. Review 092 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 2 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 092 therefore published a map with 5 keys.

### Review 093 — Slate Dock, 2024-10-04

The Slate Dock route ledger resolved `F7` for segment `NIGHT-BERTH`. Review 093 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 0 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 093 therefore published a map with 6 keys.

### Review 094 — Juniper Wharf, 2025-03-11

The Juniper Wharf route ledger resolved `D3` for segment `DRY-DOCK`. Review 094 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 1 replacement and 1 withdrawal directives changed membership; 1 required row entered before transitive closure. Review 094 therefore published a map with 7 keys.

### Review 095 — Ferry Cut, 2026-08-18

The Ferry Cut route ledger resolved `C8` for segment `TIDAL-GATE`. Review 095 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 2 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 095 therefore published a map with 3 keys.

### Review 096 — Tern Basin, 2023-01-25

Route review 096 treated selection as a graph problem rather than a top-rank query. Family `K9A` won for `COLD-QUAY`; cohort `BLUE` constrained candidate compatibility. Directives contributed 0 replacements, 0 withdrawals, and 1 requirement. Review 096 stabilized dependency closure before final deduplication, leaving 4 routes.

### Review 097 — Storm Quay, 2024-06-05

The Storm Quay route ledger resolved `K9B` for segment `WARM-PIER`. Review 097 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 1 replacement and 0 withdrawals directives changed membership; 2 required rows entered before transitive closure. Review 097 therefore published a map with 5 keys.

### Review 098 — Cinder Wharf, 2025-11-12

The Cinder Wharf review packet concerns a required route omitted because no sample called it at Cinder Wharf. The route governance board found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

Case 098 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `M4` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 2/0/1 replace-withdraw-require actions and dependency closure, 6 routes remained and every replay request had a key.

### Review 099 — Dunlin Reach, 2026-04-19

Case 099 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `S2` rather than a familiar fallback. Cohort `SILVER` excluded a newer but incompatible endpoint. After 0/1/2 replace-withdraw-require actions and dependency closure, 7 routes remained and every replay request had a key.

### Review 100 — Glass Harbor, 2023-09-26

Case 100 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `R7` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 1/1/1 replace-withdraw-require actions and dependency closure, 3 routes remained and every replay request had a key.

### Review 102 — North Quay, 2025-07-13

Case 102 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `D3` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 0/0/1 replace-withdraw-require actions and dependency closure, 5 routes remained and every replay request had a key.

### Review 104 — West Lock, 2023-05-27

Route review 104 treated selection as a graph problem rather than a top-rank query. Family `K9A` won for `DELTA`; cohort `BLUE` constrained candidate compatibility. Directives contributed 2 replacements, 0 withdrawals, and 1 requirement. Review 104 stabilized dependency closure before final deduplication, leaving 7 routes.

### Review 105 — Copper Sound, 2024-10-07

Route review 105 treated selection as a graph problem rather than a top-rank query. Family `K9B` won for `NIGHT-BERTH`; cohort `SILVER` constrained candidate compatibility. Directives contributed 0 replacements, 1 withdrawal, and 2 requirements. Review 105 stabilized dependency closure before final deduplication, leaving 3 routes.

### Review 106 — Morrow Anchorage, 2025-03-14

Case 106 entered the Morrow Anchorage register when a cohort copied from a neighboring site. The quay systems committee inherited a draft that had copied the highest visible rank. Because that draft mixed observation with authority, the board discarded its arithmetic and repeated the decision from the sealed catalog snapshot and exact HTTP bytes.

Case 106 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `M4` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 1/1/1 replace-withdraw-require actions and dependency closure, 4 routes remained and every replay request had a key.

### Review 107 — Osprey Roads, 2026-08-21

Route review 107 treated selection as a graph problem rather than a top-rank query. Family `S2` won for `TIDAL-GATE`; cohort `SILVER` constrained candidate compatibility. Directives contributed 2 replacements, 1 withdrawal, and 2 requirements. Review 107 stabilized dependency closure before final deduplication, leaving 5 routes.

### Review 108 — Heron Gate, 2023-01-01

The route governance board logged review 108 for Heron Gate following a catalog snapshot split across two generations. Its draft configuration had copied the highest visible rank, which would have passed a single-request smoke test while violating the sealed commissioning authority model. The adjudication therefore reconstructed each source boundary before considering any candidate value.

Case 108 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `R7` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 0/0/1 replace-withdraw-require actions and dependency closure, 6 routes remained and every replay request had a key.

### Review 109 — Marsh Berth, 2024-06-08

Case 109 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `F7` rather than a familiar fallback. Cohort `SILVER` excluded a newer but incompatible endpoint. After 1/0/2 replace-withdraw-require actions and dependency closure, 7 routes remained and every replay request had a key.

### Review 110 — Ash Pier, 2025-11-15

Case 110 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `D3` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 2/0/1 replace-withdraw-require actions and dependency closure, 3 routes remained and every replay request had a key.

### Review 111 — Raven Basin, 2026-04-22

The Raven Basin route ledger resolved `C8` for segment `NIGHT-BERTH`. Review 111 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 0 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 111 therefore published a map with 4 keys.

### Review 112 — Signal Jetty, 2023-09-02

Route review 112 treated selection as a graph problem rather than a top-rank query. Family `K9A` won for `DRY-DOCK`; cohort `BLUE` constrained candidate compatibility. Directives contributed 1 replacement, 1 withdrawal, and 1 requirement. Review 112 stabilized dependency closure before final deduplication, leaving 5 routes.

### Review 113 — Slate Dock, 2024-02-09

Route review 113 treated selection as a graph problem rather than a top-rank query. Family `K9B` won for `TIDAL-GATE`; cohort `SILVER` constrained candidate compatibility. Directives contributed 2 replacements, 1 withdrawal, and 2 requirements. Review 113 stabilized dependency closure before final deduplication, leaving 6 routes.

### Review 114 — Juniper Wharf, 2025-07-16

Route review 114 treated selection as a graph problem rather than a top-rank query. Family `M4` won for `COLD-QUAY`; cohort `BLUE` constrained candidate compatibility. Directives contributed 0 replacements, 0 withdrawals, and 1 requirement. Review 114 stabilized dependency closure before final deduplication, leaving 7 routes.

### Review 115 — Ferry Cut, 2026-12-23

The Ferry Cut route ledger resolved `S2` for segment `WARM-PIER`. Review 115 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 1 replacement and 0 withdrawals directives changed membership; 2 required rows entered before transitive closure. Review 115 therefore published a map with 3 keys.

### Review 116 — Tern Basin, 2023-05-03

Case 116 compared family rules by literal specificity, then source epoch, then precedence. That ordering selected `R7` rather than a familiar fallback. Cohort `BLUE` excluded a newer but incompatible endpoint. After 2/0/1 replace-withdraw-require actions and dependency closure, 4 routes remained and every replay request had a key.

### Review 117 — Storm Quay, 2024-10-10

Route review 117 treated selection as a graph problem rather than a top-rank query. Family `F7` won for `NIGHT-BERTH`; cohort `SILVER` constrained candidate compatibility. Directives contributed 0 replacements, 1 withdrawal, and 2 requirements. Review 117 stabilized dependency closure before final deduplication, leaving 5 routes.

### Review 118 — Cinder Wharf, 2025-03-17

The Cinder Wharf incident record begins when the route governance board at Cinder Wharf investigated a required route omitted because no sample called it. The initial console transcript made the highest visible rank look reasonable, but the sealed request set and catalog recovery epoch did not support that shortcut. The configuration authority documented the case because the same visible symptom had appeared in three earlier exercises with different authority sources.

Route review 118 treated selection as a graph problem rather than a top-rank query. Family `D3` won for `DRY-DOCK`; cohort `BLUE` constrained candidate compatibility. Directives contributed 1 replacement, 1 withdrawal, and 1 requirement. Review 118 stabilized dependency closure before final deduplication, leaving 6 routes.

### Review 119 — Dunlin Reach, 2026-08-24

Route review 119 treated selection as a graph problem rather than a top-rank query. Family `C8` won for `TIDAL-GATE`; cohort `SILVER` constrained candidate compatibility. Directives contributed 2 replacements, 1 withdrawal, and 2 requirements. Review 119 stabilized dependency closure before final deduplication, leaving 7 routes.

### Review 122 — North Quay, 2025-11-18

The North Quay route ledger resolved `M4` for segment `DELTA`. Review 122 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 2 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 122 therefore published a map with 5 keys.

### Review 123 — Beacon Inlet, 2026-04-25

The Beacon Inlet route ledger resolved `S2` for segment `NIGHT-BERTH`. Review 123 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 0 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 123 therefore published a map with 6 keys.

### Review 124 — West Lock, 2023-09-05

Route review 124 treated selection as a graph problem rather than a top-rank query. Family `R7` won for `DRY-DOCK`; cohort `BLUE` constrained candidate compatibility. Directives contributed 1 replacement, 1 withdrawal, and 1 requirement. Review 124 stabilized dependency closure before final deduplication, leaving 7 routes.

### Review 125 — Copper Sound, 2024-02-12

The Copper Sound route ledger resolved `F7` for segment `TIDAL-GATE`. Review 125 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 2 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 125 therefore published a map with 3 keys.

### Review 126 — Morrow Anchorage, 2025-07-19

Route review 126 treated selection as a graph problem rather than a top-rank query. Family `D3` won for `COLD-QUAY`; cohort `BLUE` constrained candidate compatibility. Directives contributed 0 replacements, 0 withdrawals, and 1 requirement. Review 126 stabilized dependency closure before final deduplication, leaving 4 routes.

At Morrow Anchorage, case 126 was opened by the quay systems committee after a cohort copied from a neighboring site. A hurried operator had copied the highest visible rank; the result looked internally consistent until the request roles were compared as one set. Reviewers reopened identity, chronology, and publication evidence instead of editing the first obviously wrong value.

### Review 128 — Heron Gate, 2023-05-06

The Heron Gate working record concerns a catalog snapshot split across two generations at Heron Gate. The route governance board found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

The Heron Gate route ledger resolved `K9A` for segment `DELTA`. Review 128 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 2 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 128 therefore published a map with 6 keys.

### Review 129 — Marsh Berth, 2024-10-13

The Marsh Berth route ledger resolved `K9B` for segment `NIGHT-BERTH`. Review 129 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 0 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 129 therefore published a map with 7 keys.

### Review 133 — Slate Dock, 2024-06-14

Route review 133 treated selection as a graph problem rather than a top-rank query. Family `F7` won for `WARM-PIER`; cohort `SILVER` constrained candidate compatibility. Directives contributed 1 replacement, 0 withdrawals, and 2 requirements. Review 133 stabilized dependency closure before final deduplication, leaving 6 routes.

### Review 134 — Juniper Wharf, 2025-11-21

The Juniper Wharf route ledger resolved `D3` for segment `DELTA`. Review 134 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 2 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 134 therefore published a map with 7 keys.

### Review 135 — Ferry Cut, 2026-04-01

Route review 135 treated selection as a graph problem rather than a top-rank query. Family `C8` won for `NIGHT-BERTH`; cohort `SILVER` constrained candidate compatibility. Directives contributed 0 replacements, 1 withdrawal, and 2 requirements. Review 135 stabilized dependency closure before final deduplication, leaving 3 routes.

### Review 137 — Storm Quay, 2024-02-15

The Storm Quay route ledger resolved `K9B` for segment `TIDAL-GATE`. Review 137 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `SILVER`, base candidates were deduplicated, then 2 replacements and 1 withdrawal directives changed membership; 2 required rows entered before transitive closure. Review 137 therefore published a map with 5 keys.

### Review 138 — Cinder Wharf, 2025-07-22

The Cinder Wharf review packet concerns a required route omitted because no sample called it at Cinder Wharf. The route governance board found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

### Review 139 — Dunlin Reach, 2026-12-02

Route review 139 treated selection as a graph problem rather than a top-rank query. Family `S2` won for `WARM-PIER`; cohort `SILVER` constrained candidate compatibility. Directives contributed 1 replacement, 0 withdrawals, and 2 requirements. Review 139 stabilized dependency closure before final deduplication, leaving 7 routes.

### Review 140 — Glass Harbor, 2023-05-09

The Glass Harbor route ledger resolved `R7` for segment `DELTA`. Review 140 rejected a numerically stronger legacy rule because its source epoch was older. Within cohort `BLUE`, base candidates were deduplicated, then 2 replacements and 0 withdrawals directives changed membership; 1 required row entered before transitive closure. Review 140 therefore published a map with 3 keys.


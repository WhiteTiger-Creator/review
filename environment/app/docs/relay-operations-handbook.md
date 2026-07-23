# Harbor Relay Operations Handbook

Revision HRH-2026.07-R11

This volume establishes authority boundaries for a sealed relay recovery. It is deliberately paired with four companion records: socket evidence, route governance, capacity and payload adjudication, and publication assurance. No volume is a summary of the others. Operators must reconcile the set because request identity, catalog authority, chronology, graph closure, arithmetic, and transactional publication become authoritative at different stages. Historical records below are precedents for interpreting those boundaries; their numeric values are never reusable defaults.

## Policy chapter 1: Authority boundaries and sealed evidence

The enabled deployment context is authoritative only after a request alias is resolved at the context recovery epoch. A request cannot invent a site, a trace cannot authorize a path absent from the catalog, and lsof cannot make a catalog-disabled endpoint valid. Capture metadata seals chronology and handbook revision. A revision mismatch invalidates the whole set rather than downgrading one source. The request-set digest is over role, absolute path, byte length, and file digest in manifest order; the evidence-set digest is over capture metadata, strace, and lsof descriptors in that order.

A complete recovery treats every request in the manifest as one demand set. Site alias, segment, and replay mode must agree across the set. The largest decoded body controls envelope selection; the number of requests and the presence of custody replay can activate independent adjustments. A body length is measured in bytes after the HTTP separator. Declared and observed lengths must match exactly, including UTF-8 multibyte data.

## Policy chapter 2: Alias adjudication

Alias rows are compared at the chosen deployment context's recovery epoch using closed intervals. Disabled aliases do not participate. When an alias names more than one enabled context, later effective-from wins, then higher precedence rank. If those dimensions tie across different sites, identity is ambiguous and recovery fails. A literal site key has no special privilege unless represented by an alias row. The selected context generation must equal catalog_meta.catalog_generation.

Recovery does not choose a context first and then search for an alias that supports it. It evaluates enabled contexts reachable from the alias, applies temporal validity, then precedence. This distinction matters in restored catalogs where a retired site retains a high advisory rank outside the active interval.

## Policy chapter 3: Batch catalog snapshot

The catalog boundary is one batch command invocation. A recovery asks for all policy tables needed to prove a decision and hashes the normalized result blocks in query-name order. Re-querying after partial derivation is prohibited because it can combine generations. Missing or extra result blocks, duplicate headers, malformed row widths, mutation-capable SQL, or a generation mismatch invalidate the snapshot. The snapshot digest covers the exact normalized TSV block representation, not the opaque database file.

## Policy chapter 9: Planning, validation, and deterministic identity

Plan and apply derive the same logical state. Planning computes exact bytes, permissions, assertions, and publication digests without changing the filesystem. The run ID is the first 24 lowercase hex characters of SHA-256 over the handbook revision, catalog generation, selected site, request-set digest, evidence-set digest, catalog snapshot digest, and the three generated text file digests separated by newlines. Paths are included indirectly through input and publication objects, so relocated roots produce a different identity.

All catalog audit rules must be represented. Assertions are not optimistic declarations: each is emitted only after the associated invariant has been checked. The staged relay validator proves syntax and route readability but does not replace independent checks of provenance, arithmetic, directives, and digests.

## Policy chapter 12: Relocation and command substitution

A relocated root changes only root-relative installation paths. Explicit request, evidence, audit, manifest, or catalog command options are not rewritten. Catalog path templates may contain exactly one `{root}` token. A template escaping the root after lexical normalization is invalid. The alternate catalog command is treated as an opaque executable; recovery must not assume the location or existence of its backing database.

## Review archive

The records are ordered by review number, not by precedence. Current recovery inputs remain controlling. Cross-references with the same review number in companion volumes describe another domain of the same event.

### Review 001 — Lantern Terminal, 2024-06-08

The request bundle in case 001 used `lantern-terminal-2`, not a raw site key. Temporal alias adjudication reached `st-137` because 2024-06-01T00:00:00Z fell inside the selected row's closed interval. The operations council rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `WARM-PIER`.

### Review 002 — North Quay, 2025-11-15

The North Quay identity review compared alias `north-quay-3` across closed intervals. The winning row became effective on 2025-11-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 002 treated a literal site key like any other alias evidence. Every request role carried segment `DELTA` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 003 — Beacon Inlet, 2026-04-22

The Beacon Inlet record demonstrates that a filesystem path cannot establish site identity. Alias `beacon-inlet-4` resolved to `st-211` only after the enabled contexts were filtered at generation 61. The three request roles agreed on `NIGHT-BERTH` and `custody`; the matching headers were evidence only; the catalog remained decisive in review 003.

### Review 004 — West Lock, 2023-09-02

The request bundle in case 004 used `west-lock-5`, not a raw site key. Temporal alias adjudication reached `st-248` because 2023-09-01T00:00:00Z fell inside the selected row's closed interval. The recovery board rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DRY-DOCK`.

### Review 005 — Copper Sound, 2024-02-09

The Copper Sound record demonstrates that a filesystem path cannot establish site identity. Alias `copper-sound-6` resolved to `st-285` only after the enabled contexts were filtered at generation 12. The three request roles agreed on `TIDAL-GATE` and `observe`; header agreement established consistency without replacing catalog authority in review 005.

### Review 006 — Morrow Anchorage, 2025-07-16

The request bundle in case 006 used `morrow-anchorage-7`, not a raw site key. Temporal alias adjudication reached `st-322` because 2025-07-01T00:00:00Z fell inside the selected row's closed interval. The on-call review cell rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `COLD-QUAY`.

### Review 007 — Osprey Roads, 2026-12-23

The Osprey Roads record demonstrates that a filesystem path cannot establish site identity. Alias `osprey-roads-8` resolved to `st-359` only after the enabled contexts were filtered at generation 46. The three request roles agreed on `WARM-PIER` and `custody`; the requests corroborated each other, but only the catalog could authorize the alias in review 007.

### Review 008 — Heron Gate, 2023-05-03

For 008, the alias ledger showed `heron-gate-9` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-396` at generation 63. It also verified that all request files agreed on `DELTA` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 009 — Marsh Berth, 2024-10-10

The request bundle in case 009 used `marsh-berth-1`, not a raw site key. Temporal alias adjudication reached `st-433` because 2024-10-01T00:00:00Z fell inside the selected row's closed interval. The relay assurance committee rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `NIGHT-BERTH`.

### Review 010 — Ash Pier, 2025-03-17

The Ash Pier identity review compared alias `ash-pier-2` across closed intervals. The winning row became effective on 2025-03-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 010 treated a literal site key like any other alias evidence. Every request role carried segment `DRY-DOCK` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 011 — Raven Basin, 2026-08-24

For 011, the alias ledger showed `raven-basin-3` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-507` at generation 31. It also verified that all request files agreed on `TIDAL-GATE` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 012 — Signal Jetty, 2023-01-04

The Signal Jetty incident record begins when the catalog operations desk at Signal Jetty investigated a disabled adjustment treated as current. The initial console transcript made the highest visible rank look reasonable, but the sealed request set and catalog recovery epoch did not support that shortcut. The catalog governance team preserved the case because the same visible symptom had appeared in three earlier exercises with different authority sources.

For 012, the alias ledger showed `signal-jetty-4` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-544` at generation 48. It also verified that all request files agreed on `COLD-QUAY` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 014 — Juniper Wharf, 2025-11-18

For 014, the alias ledger showed `juniper-wharf-6` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-618` at generation 82. It also verified that all request files agreed on `DELTA` and `sealed` and that the capture metadata named the same handbook revision as the catalog.

### Review 015 — Ferry Cut, 2026-04-25

The Ferry Cut identity review compared alias `ferry-cut-7` across closed intervals. The winning row became effective on 2026-04-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 015 did not let literal spelling bypass alias adjudication. Every request role carried segment `NIGHT-BERTH` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 016 — Tern Basin, 2023-09-05

The request bundle in case 016 used `tern-basin-8`, not a raw site key. Temporal alias adjudication reached `st-692` because 2023-09-01T00:00:00Z fell inside the selected row's closed interval. The on-call review cell rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DRY-DOCK`.

### Review 017 — Storm Quay, 2024-02-12

The Storm Quay record demonstrates that a filesystem path cannot establish site identity. Alias `storm-quay-9` resolved to `st-729` only after the enabled contexts were filtered at generation 50. The three request roles agreed on `TIDAL-GATE` and `observe`; their agreement supported consistency, while the catalog still decided alias usability in review 017.

### Review 018 — Cinder Wharf, 2025-07-19

The Cinder Wharf identity review compared alias `cinder-wharf-1` across closed intervals. The winning row became effective on 2025-07-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 018 treated a literal site key like any other alias evidence. Every request role carried segment `COLD-QUAY` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 019 — Dunlin Reach, 2026-12-26

The request bundle in case 019 used `dunlin-reach-2`, not a raw site key. Temporal alias adjudication reached `st-803` because 2026-12-01T00:00:00Z fell inside the selected row's closed interval. The relay assurance committee rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `WARM-PIER`.

### Review 020 — Glass Harbor, 2023-05-06

For 020, the alias ledger showed `glass-harbor-3` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-840` at generation 18. It also verified that all request files agreed on `DELTA` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 021 — Lantern Terminal, 2024-10-13

The request bundle in case 021 used `lantern-terminal-4`, not a raw site key. Temporal alias adjudication reached `st-877` because 2024-10-01T00:00:00Z fell inside the selected row's closed interval. The operations council rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `NIGHT-BERTH`.

### Review 022 — North Quay, 2025-03-20

The North Quay identity review compared alias `north-quay-5` across closed intervals. The winning row became effective on 2025-03-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 022 gave a literal key no special precedence. Every request role carried segment `DRY-DOCK` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 023 — Beacon Inlet, 2026-08-27

The Beacon Inlet record demonstrates that a filesystem path cannot establish site identity. Alias `beacon-inlet-6` resolved to `st-951` only after the enabled contexts were filtered at generation 69. The three request roles agreed on `TIDAL-GATE` and `custody`; the requests corroborated each other, but only the catalog could authorize the alias in review 023.

### Review 025 — Copper Sound, 2024-06-14

The request bundle in case 025 used `copper-sound-8`, not a raw site key. Temporal alias adjudication reached `st-125` because 2024-06-01T00:00:00Z fell inside the selected row's closed interval. The service continuity group rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `WARM-PIER`.

### Review 026 — Morrow Anchorage, 2025-11-21

The Morrow Anchorage record demonstrates that a filesystem path cannot establish site identity. Alias `morrow-anchorage-9` resolved to `st-162` only after the enabled contexts were filtered at generation 37. The three request roles agreed on `DELTA` and `sealed`; their agreement proved a coherent request set, but catalog authority controlled alias eligibility in review 026.

### Review 027 — Osprey Roads, 2026-04-01

For 027, the alias ledger showed `osprey-roads-1` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-199` at generation 54. It also verified that all request files agreed on `NIGHT-BERTH` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 028 — Heron Gate, 2023-09-08

The request bundle in case 028 used `heron-gate-2`, not a raw site key. Temporal alias adjudication reached `st-236` because 2023-09-01T00:00:00Z fell inside the selected row's closed interval. The evidence panel rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DRY-DOCK`.

### Review 029 — Marsh Berth, 2024-02-15

For 029, the alias ledger showed `marsh-berth-3` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-273` at generation 88. It also verified that all request files agreed on `TIDAL-GATE` and `observe` and that the capture metadata named the same handbook revision as the catalog.

### Review 030 — Ash Pier, 2025-07-22

The request bundle in case 030 used `ash-pier-4`, not a raw site key. Temporal alias adjudication reached `st-310` because 2025-07-01T00:00:00Z fell inside the selected row's closed interval. The harbor systems panel rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `COLD-QUAY`.

### Review 031 — Raven Basin, 2026-12-02

For 031, the alias ledger showed `raven-basin-5` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-347` at generation 39. It also verified that all request files agreed on `WARM-PIER` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 032 — Signal Jetty, 2023-05-09

The Signal Jetty review packet concerns a disabled adjustment treated as current at Signal Jetty. The catalog operations desk found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

The Signal Jetty identity review compared alias `signal-jetty-6` across closed intervals. The winning row became effective on 2023-05-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 032 required the same alias proof for literal and nonliteral values. Every request role carried segment `DELTA` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 033 — Slate Dock, 2024-10-16

The Slate Dock record demonstrates that a filesystem path cannot establish site identity. Alias `slate-dock-7` resolved to `st-421` only after the enabled contexts were filtered at generation 73. The three request roles agreed on `NIGHT-BERTH` and `observe`; their agreement supported consistency, while the catalog still decided alias usability in review 033.

### Review 034 — Juniper Wharf, 2025-03-23

The Juniper Wharf identity review compared alias `juniper-wharf-8` across closed intervals. The winning row became effective on 2025-03-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 034 treated a literal site key like any other alias evidence. Every request role carried segment `DRY-DOCK` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 035 — Ferry Cut, 2026-08-03

The Ferry Cut record demonstrates that a filesystem path cannot establish site identity. Alias `ferry-cut-9` resolved to `st-495` only after the enabled contexts were filtered at generation 24. The three request roles agreed on `TIDAL-GATE` and `custody`; the matching headers were evidence only; the catalog remained decisive in review 035.

### Review 036 — Tern Basin, 2023-01-10

The Tern Basin identity review compared alias `tern-basin-1` across closed intervals. The winning row became effective on 2023-01-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 036 required catalog-backed alias authority even for a literal-looking key. Every request role carried segment `COLD-QUAY` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 037 — Storm Quay, 2024-06-17

For 037, the alias ledger showed `storm-quay-2` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-569` at generation 58. It also verified that all request files agreed on `WARM-PIER` and `observe` and that the capture metadata named the same handbook revision as the catalog.

### Review 038 — Cinder Wharf, 2025-11-24

The Cinder Wharf record demonstrates that a filesystem path cannot establish site identity. Alias `cinder-wharf-3` resolved to `st-606` only after the enabled contexts were filtered at generation 75. The three request roles agreed on `DELTA` and `sealed`; the shared values supported identity reasoning, while alias authorization remained catalog-controlled in review 038.

### Review 039 — Dunlin Reach, 2026-04-04

The Dunlin Reach record demonstrates that a filesystem path cannot establish site identity. Alias `dunlin-reach-4` resolved to `st-643` only after the enabled contexts were filtered at generation 92. The three request roles agreed on `NIGHT-BERTH` and `custody`; the requests corroborated each other, but only the catalog could authorize the alias in review 039.

### Review 040 — Glass Harbor, 2023-09-11

The Glass Harbor identity review compared alias `glass-harbor-5` across closed intervals. The winning row became effective on 2023-09-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 040 required the same alias proof for literal and nonliteral values. Every request role carried segment `DRY-DOCK` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 041 — Lantern Terminal, 2024-02-18

For 041, the alias ledger showed `lantern-terminal-6` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-717` at generation 43. It also verified that all request files agreed on `TIDAL-GATE` and `observe` and that the capture metadata named the same handbook revision as the catalog.

### Review 042 — North Quay, 2025-07-25

The request bundle in case 042 used `north-quay-7`, not a raw site key. Temporal alias adjudication reached `st-754` because 2025-07-01T00:00:00Z fell inside the selected row's closed interval. The catalog governance team rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `COLD-QUAY`.

### Review 043 — Beacon Inlet, 2026-12-05

The Beacon Inlet identity review compared alias `beacon-inlet-8` across closed intervals. The winning row became effective on 2026-12-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 043 allowed no shortcut merely because a token resembled a site key. Every request role carried segment `WARM-PIER` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 045 — Copper Sound, 2024-10-19

The request bundle in case 045 used `copper-sound-1`, not a raw site key. Temporal alias adjudication reached `st-865` because 2024-10-01T00:00:00Z fell inside the selected row's closed interval. The service continuity group rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `NIGHT-BERTH`.

### Review 046 — Morrow Anchorage, 2025-03-26

For 046, the alias ledger showed `morrow-anchorage-2` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-902` at generation 45. It also verified that all request files agreed on `DRY-DOCK` and `sealed` and that the capture metadata named the same handbook revision as the catalog.

### Review 047 — Osprey Roads, 2026-08-06

The request bundle in case 047 used `osprey-roads-3`, not a raw site key. Temporal alias adjudication reached `st-939` because 2026-08-01T00:00:00Z fell inside the selected row's closed interval. The configuration authority rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `TIDAL-GATE`.

### Review 048 — Heron Gate, 2023-01-13

The Heron Gate record demonstrates that a filesystem path cannot establish site identity. Alias `heron-gate-4` resolved to `st-976` only after the enabled contexts were filtered at generation 79. The three request roles agreed on `COLD-QUAY` and `custody`; the common headers were supporting evidence, not an authority substitute, in review 048.

### Review 049 — Marsh Berth, 2024-06-20

The request bundle in case 049 used `marsh-berth-5`, not a raw site key. Temporal alias adjudication reached `st-113` because 2024-06-01T00:00:00Z fell inside the selected row's closed interval. The relay assurance committee rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `WARM-PIER`.

### Review 050 — Ash Pier, 2025-11-27

The Ash Pier identity review compared alias `ash-pier-6` across closed intervals. The winning row became effective on 2025-11-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 050 treated a literal site key like any other alias evidence. Every request role carried segment `DELTA` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 051 — Raven Basin, 2026-04-07

For 051, the alias ledger showed `raven-basin-7` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-187` at generation 47. It also verified that all request files agreed on `NIGHT-BERTH` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 052 — Signal Jetty, 2023-09-14

The Signal Jetty record demonstrates that a filesystem path cannot establish site identity. Alias `signal-jetty-8` resolved to `st-224` only after the enabled contexts were filtered at generation 64. The three request roles agreed on `DRY-DOCK` and `custody`; the request set agreed internally, yet catalog policy still authorized the alias in review 052.

### Review 054 — Juniper Wharf, 2025-07-01

For 054, the alias ledger showed `juniper-wharf-1` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-298` at generation 15. It also verified that all request files agreed on `COLD-QUAY` and `sealed` and that the capture metadata named the same handbook revision as the catalog.

### Review 055 — Ferry Cut, 2026-12-08

The Ferry Cut identity review compared alias `ferry-cut-2` across closed intervals. The winning row became effective on 2026-12-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 055 did not let literal spelling bypass alias adjudication. Every request role carried segment `WARM-PIER` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 056 — Tern Basin, 2023-05-15

The request bundle in case 056 used `tern-basin-3`, not a raw site key. Temporal alias adjudication reached `st-372` because 2023-05-01T00:00:00Z fell inside the selected row's closed interval. The on-call review cell rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DELTA`.

### Review 057 — Storm Quay, 2024-10-22

The Storm Quay record demonstrates that a filesystem path cannot establish site identity. Alias `storm-quay-4` resolved to `st-409` only after the enabled contexts were filtered at generation 66. The three request roles agreed on `NIGHT-BERTH` and `observe`; their agreement supported consistency, while the catalog still decided alias usability in review 057.

### Review 058 — Cinder Wharf, 2025-03-02

The Cinder Wharf identity review compared alias `cinder-wharf-5` across closed intervals. The winning row became effective on 2025-03-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 058 treated a literal site key like any other alias evidence. Every request role carried segment `DRY-DOCK` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 059 — Dunlin Reach, 2026-08-09

The request bundle in case 059 used `dunlin-reach-6`, not a raw site key. Temporal alias adjudication reached `st-483` because 2026-08-01T00:00:00Z fell inside the selected row's closed interval. The relay assurance committee rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `TIDAL-GATE`.

### Review 060 — Glass Harbor, 2023-01-16

For 060, the alias ledger showed `glass-harbor-7` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-520` at generation 34. It also verified that all request files agreed on `COLD-QUAY` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 061 — Lantern Terminal, 2024-06-23

The Lantern Terminal identity review compared alias `lantern-terminal-8` across closed intervals. The winning row became effective on 2024-06-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 061 refused to elevate a literal site key above alias policy. Every request role carried segment `WARM-PIER` and replay posture `observe`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 062 — North Quay, 2025-11-03

The request bundle in case 062 used `north-quay-9`, not a raw site key. Temporal alias adjudication reached `st-594` because 2025-11-01T00:00:00Z fell inside the selected row's closed interval. The catalog governance team rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DELTA`.

### Review 065 — Copper Sound, 2024-02-24

The Copper Sound identity review compared alias `copper-sound-3` across closed intervals. The winning row became effective on 2024-02-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 065 did not privilege a literal site key. Every request role carried segment `TIDAL-GATE` and replay posture `observe`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 066 — Morrow Anchorage, 2025-07-04

The request bundle in case 066 used `morrow-anchorage-4`, not a raw site key. Temporal alias adjudication reached `st-742` because 2025-07-01T00:00:00Z fell inside the selected row's closed interval. The on-call review cell rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `COLD-QUAY`.

### Review 067 — Osprey Roads, 2026-12-11

The Osprey Roads identity review compared alias `osprey-roads-5` across closed intervals. The winning row became effective on 2026-12-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 067 allowed no shortcut merely because a token resembled a site key. Every request role carried segment `WARM-PIER` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 068 — Heron Gate, 2023-05-18

The Heron Gate record demonstrates that a filesystem path cannot establish site identity. Alias `heron-gate-6` resolved to `st-816` only after the enabled contexts were filtered at generation 87. The three request roles agreed on `DELTA` and `custody`; the request set agreed internally, yet catalog policy still authorized the alias in review 068.

### Review 069 — Marsh Berth, 2024-10-25

The Marsh Berth identity review compared alias `marsh-berth-7` across closed intervals. The winning row became effective on 2024-10-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 069 refused to elevate a literal site key above alias policy. Every request role carried segment `NIGHT-BERTH` and replay posture `observe`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 070 — Ash Pier, 2025-03-05

For 070, the alias ledger showed `ash-pier-8` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-890` at generation 38. It also verified that all request files agreed on `DRY-DOCK` and `sealed` and that the capture metadata named the same handbook revision as the catalog.

### Review 071 — Raven Basin, 2026-08-12

The request bundle in case 071 used `raven-basin-9`, not a raw site key. Temporal alias adjudication reached `st-927` because 2026-08-01T00:00:00Z fell inside the selected row's closed interval. The operations council rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `TIDAL-GATE`.

### Review 072 — Signal Jetty, 2023-01-19

For 072, the alias ledger showed `signal-jetty-1` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-964` at generation 72. It also verified that all request files agreed on `COLD-QUAY` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 074 — Juniper Wharf, 2025-11-06

The Juniper Wharf record demonstrates that a filesystem path cannot establish site identity. Alias `juniper-wharf-3` resolved to `st-138` only after the enabled contexts were filtered at generation 23. The three request roles agreed on `DELTA` and `sealed`; their agreement proved a coherent request set, but catalog authority controlled alias eligibility in review 074.

### Review 075 — Ferry Cut, 2026-04-13

The Ferry Cut identity review compared alias `ferry-cut-4` across closed intervals. The winning row became effective on 2026-04-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 075 allowed no shortcut merely because a token resembled a site key. Every request role carried segment `NIGHT-BERTH` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 076 — Tern Basin, 2023-09-20

The request bundle in case 076 used `tern-basin-5`, not a raw site key. Temporal alias adjudication reached `st-212` because 2023-09-01T00:00:00Z fell inside the selected row's closed interval. The on-call review cell rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DRY-DOCK`.

### Review 077 — Storm Quay, 2024-02-27

The request bundle in case 077 used `storm-quay-6`, not a raw site key. Temporal alias adjudication reached `st-249` because 2024-02-01T00:00:00Z fell inside the selected row's closed interval. The configuration authority rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `TIDAL-GATE`.

### Review 078 — Cinder Wharf, 2025-07-07

The request bundle in case 078 used `cinder-wharf-7`, not a raw site key. Temporal alias adjudication reached `st-286` because 2025-07-01T00:00:00Z fell inside the selected row's closed interval. The evidence panel rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `COLD-QUAY`.

### Review 079 — Dunlin Reach, 2026-12-14

The request bundle in case 079 used `dunlin-reach-8`, not a raw site key. Temporal alias adjudication reached `st-323` because 2026-12-01T00:00:00Z fell inside the selected row's closed interval. The relay assurance committee rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `WARM-PIER`.

### Review 080 — Glass Harbor, 2023-05-21

The Glass Harbor record demonstrates that a filesystem path cannot establish site identity. Alias `glass-harbor-9` resolved to `st-360` only after the enabled contexts were filtered at generation 42. The three request roles agreed on `DELTA` and `custody`; the common headers were supporting evidence, not an authority substitute, in review 080.

### Review 081 — Lantern Terminal, 2024-10-01

The request bundle in case 081 used `lantern-terminal-1`, not a raw site key. Temporal alias adjudication reached `st-397` because 2024-10-01T00:00:00Z fell inside the selected row's closed interval. The operations council rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `NIGHT-BERTH`.

### Review 082 — North Quay, 2025-03-08

For 082, the alias ledger showed `north-quay-2` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-434` at generation 76. It also verified that all request files agreed on `DRY-DOCK` and `sealed` and that the capture metadata named the same handbook revision as the catalog.

### Review 083 — Beacon Inlet, 2026-08-15

The Beacon Inlet record demonstrates that a filesystem path cannot establish site identity. Alias `beacon-inlet-3` resolved to `st-471` only after the enabled contexts were filtered at generation 10. The three request roles agreed on `TIDAL-GATE` and `custody`; the matching headers were evidence only; the catalog remained decisive in review 083.

### Review 084 — West Lock, 2023-01-22

The request bundle in case 084 used `west-lock-4`, not a raw site key. Temporal alias adjudication reached `st-508` because 2023-01-01T00:00:00Z fell inside the selected row's closed interval. The recovery board rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `COLD-QUAY`.

### Review 085 — Copper Sound, 2024-06-02

The Copper Sound identity review compared alias `copper-sound-5` across closed intervals. The winning row became effective on 2024-06-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 085 refused to elevate a literal site key above alias policy. Every request role carried segment `WARM-PIER` and replay posture `observe`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 086 — Morrow Anchorage, 2025-11-09

For 086, the alias ledger showed `morrow-anchorage-6` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-582` at generation 61. It also verified that all request files agreed on `DELTA` and `sealed` and that the capture metadata named the same handbook revision as the catalog.

### Review 087 — Osprey Roads, 2026-04-16

The Osprey Roads record demonstrates that a filesystem path cannot establish site identity. Alias `osprey-roads-7` resolved to `st-619` only after the enabled contexts were filtered at generation 78. The three request roles agreed on `NIGHT-BERTH` and `custody`; the requests corroborated each other, but only the catalog could authorize the alias in review 087.

### Review 088 — Heron Gate, 2023-09-23

The Heron Gate identity review compared alias `heron-gate-8` across closed intervals. The winning row became effective on 2023-09-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 088 required the same alias proof for literal and nonliteral values. Every request role carried segment `DRY-DOCK` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 089 — Marsh Berth, 2024-02-03

The request bundle in case 089 used `marsh-berth-9`, not a raw site key. Temporal alias adjudication reached `st-693` because 2024-02-01T00:00:00Z fell inside the selected row's closed interval. The relay assurance committee rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `TIDAL-GATE`.

### Review 090 — Ash Pier, 2025-07-10

The Ash Pier record demonstrates that a filesystem path cannot establish site identity. Alias `ash-pier-1` resolved to `st-730` only after the enabled contexts were filtered at generation 46. The three request roles agreed on `COLD-QUAY` and `sealed`; their agreement proved a coherent request set, but catalog authority controlled alias eligibility in review 090.

### Review 091 — Raven Basin, 2026-12-17

The request bundle in case 091 used `raven-basin-2`, not a raw site key. Temporal alias adjudication reached `st-767` because 2026-12-01T00:00:00Z fell inside the selected row's closed interval. The operations council rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `WARM-PIER`.

### Review 092 — Signal Jetty, 2023-05-24

The Signal Jetty review packet concerns a disabled adjustment treated as current at Signal Jetty. The catalog operations desk found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

For 092, the alias ledger showed `signal-jetty-3` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-804` at generation 80. It also verified that all request files agreed on `DELTA` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 093 — Slate Dock, 2024-10-04

For 093, the alias ledger showed `slate-dock-4` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-841` at generation 14. It also verified that all request files agreed on `NIGHT-BERTH` and `observe` and that the capture metadata named the same handbook revision as the catalog.

### Review 094 — Juniper Wharf, 2025-03-11

The Juniper Wharf identity review compared alias `juniper-wharf-5` across closed intervals. The winning row became effective on 2025-03-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 094 gave a literal key no special precedence. Every request role carried segment `DRY-DOCK` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 095 — Ferry Cut, 2026-08-18

For 095, the alias ledger showed `ferry-cut-6` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-915` at generation 48. It also verified that all request files agreed on `TIDAL-GATE` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 096 — Tern Basin, 2023-01-25

For 096, the alias ledger showed `tern-basin-7` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-952` at generation 65. It also verified that all request files agreed on `COLD-QUAY` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 097 — Storm Quay, 2024-06-05

The Storm Quay identity review compared alias `storm-quay-8` across closed intervals. The winning row became effective on 2024-06-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 097 did not privilege a literal site key. Every request role carried segment `WARM-PIER` and replay posture `observe`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 098 — Cinder Wharf, 2025-11-12

The request bundle in case 098 used `cinder-wharf-9`, not a raw site key. Temporal alias adjudication reached `st-126` because 2025-11-01T00:00:00Z fell inside the selected row's closed interval. The evidence panel rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DELTA`.

### Review 099 — Dunlin Reach, 2026-04-19

For 099, the alias ledger showed `dunlin-reach-1` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-163` at generation 33. It also verified that all request files agreed on `NIGHT-BERTH` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 100 — Glass Harbor, 2023-09-26

For 100, the alias ledger showed `glass-harbor-2` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-200` at generation 50. It also verified that all request files agreed on `DRY-DOCK` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 101 — Lantern Terminal, 2024-02-06

The Lantern Terminal record demonstrates that a filesystem path cannot establish site identity. Alias `lantern-terminal-3` resolved to `st-237` only after the enabled contexts were filtered at generation 67. The three request roles agreed on `TIDAL-GATE` and `observe`; header agreement established consistency without replacing catalog authority in review 101.

### Review 102 — North Quay, 2025-07-13

The request bundle in case 102 used `north-quay-4`, not a raw site key. Temporal alias adjudication reached `st-274` because 2025-07-01T00:00:00Z fell inside the selected row's closed interval. The catalog governance team rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `COLD-QUAY`.

### Review 103 — Beacon Inlet, 2026-12-20

For 103, the alias ledger showed `beacon-inlet-5` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-311` at generation 18. It also verified that all request files agreed on `WARM-PIER` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 104 — West Lock, 2023-05-27

The request bundle in case 104 used `west-lock-6`, not a raw site key. Temporal alias adjudication reached `st-348` because 2023-05-01T00:00:00Z fell inside the selected row's closed interval. The recovery board rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DELTA`.

### Review 105 — Copper Sound, 2024-10-07

The Copper Sound record demonstrates that a filesystem path cannot establish site identity. Alias `copper-sound-7` resolved to `st-385` only after the enabled contexts were filtered at generation 52. The three request roles agreed on `NIGHT-BERTH` and `observe`; their agreement supported consistency, while the catalog still decided alias usability in review 105.

### Review 106 — Morrow Anchorage, 2025-03-14

The request bundle in case 106 used `morrow-anchorage-8`, not a raw site key. Temporal alias adjudication reached `st-422` because 2025-03-01T00:00:00Z fell inside the selected row's closed interval. The on-call review cell rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DRY-DOCK`.

### Review 107 — Osprey Roads, 2026-08-21

The Osprey Roads record demonstrates that a filesystem path cannot establish site identity. Alias `osprey-roads-9` resolved to `st-459` only after the enabled contexts were filtered at generation 86. The three request roles agreed on `TIDAL-GATE` and `custody`; the matching headers were evidence only; the catalog remained decisive in review 107.

### Review 108 — Heron Gate, 2023-01-01

For 108, the alias ledger showed `heron-gate-1` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-496` at generation 20. It also verified that all request files agreed on `COLD-QUAY` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 109 — Marsh Berth, 2024-06-08

The request bundle in case 109 used `marsh-berth-2`, not a raw site key. Temporal alias adjudication reached `st-533` because 2024-06-01T00:00:00Z fell inside the selected row's closed interval. The relay assurance committee rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `WARM-PIER`.

### Review 110 — Ash Pier, 2025-11-15

The request bundle in case 110 used `ash-pier-3`, not a raw site key. Temporal alias adjudication reached `st-570` because 2025-11-01T00:00:00Z fell inside the selected row's closed interval. The harbor systems panel rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DELTA`.

### Review 111 — Raven Basin, 2026-04-22

The request bundle in case 111 used `raven-basin-4`, not a raw site key. Temporal alias adjudication reached `st-607` because 2026-04-01T00:00:00Z fell inside the selected row's closed interval. The operations council rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `NIGHT-BERTH`.

### Review 112 — Signal Jetty, 2023-09-02

The Signal Jetty incident record begins when the catalog operations desk at Signal Jetty investigated a disabled adjustment treated as current. The initial console transcript made the highest visible rank look reasonable, but the sealed request set and catalog recovery epoch did not support that shortcut. The catalog governance team preserved the case because the same visible symptom had appeared in three earlier exercises with different authority sources.

The Signal Jetty identity review compared alias `signal-jetty-5` across closed intervals. The winning row became effective on 2023-09-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 112 required the same alias proof for literal and nonliteral values. Every request role carried segment `DRY-DOCK` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 113 — Slate Dock, 2024-02-09

The Slate Dock identity review compared alias `slate-dock-6` across closed intervals. The winning row became effective on 2024-02-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 113 did not privilege a literal site key. Every request role carried segment `TIDAL-GATE` and replay posture `observe`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 114 — Juniper Wharf, 2025-07-16

The Juniper Wharf record demonstrates that a filesystem path cannot establish site identity. Alias `juniper-wharf-7` resolved to `st-718` only after the enabled contexts were filtered at generation 39. The three request roles agreed on `COLD-QUAY` and `sealed`; their agreement proved a coherent request set, but catalog authority controlled alias eligibility in review 114.

### Review 115 — Ferry Cut, 2026-12-23

For 115, the alias ledger showed `ferry-cut-8` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-755` at generation 56. It also verified that all request files agreed on `WARM-PIER` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 116 — Tern Basin, 2023-05-03

The request bundle in case 116 used `tern-basin-9`, not a raw site key. Temporal alias adjudication reached `st-792` because 2023-05-01T00:00:00Z fell inside the selected row's closed interval. The on-call review cell rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `DELTA`.

### Review 117 — Storm Quay, 2024-10-10

For 117, the alias ledger showed `storm-quay-1` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-829` at generation 90. It also verified that all request files agreed on `NIGHT-BERTH` and `observe` and that the capture metadata named the same handbook revision as the catalog.

### Review 118 — Cinder Wharf, 2025-03-17

The Cinder Wharf identity review compared alias `cinder-wharf-2` across closed intervals. The winning row became effective on 2025-03-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 118 gave a literal key no special precedence. Every request role carried segment `DRY-DOCK` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 119 — Dunlin Reach, 2026-08-24

The Dunlin Reach identity review compared alias `dunlin-reach-3` across closed intervals. The winning row became effective on 2026-08-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 119 did not let literal spelling bypass alias adjudication. Every request role carried segment `TIDAL-GATE` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 120 — Glass Harbor, 2023-01-04

For 120, the alias ledger showed `glass-harbor-4` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-940` at generation 58. It also verified that all request files agreed on `COLD-QUAY` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 121 — Lantern Terminal, 2024-06-11

The request bundle in case 121 used `lantern-terminal-5`, not a raw site key. Temporal alias adjudication reached `st-977` because 2024-06-01T00:00:00Z fell inside the selected row's closed interval. The operations council rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `WARM-PIER`.

### Review 122 — North Quay, 2025-11-18

The North Quay record demonstrates that a filesystem path cannot establish site identity. Alias `north-quay-6` resolved to `st-114` only after the enabled contexts were filtered at generation 92. The three request roles agreed on `DELTA` and `sealed`; their agreement proved a coherent request set, but catalog authority controlled alias eligibility in review 122.

### Review 123 — Beacon Inlet, 2026-04-25

The Beacon Inlet identity review compared alias `beacon-inlet-7` across closed intervals. The winning row became effective on 2026-04-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 123 allowed no shortcut merely because a token resembled a site key. Every request role carried segment `NIGHT-BERTH` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 125 — Copper Sound, 2024-02-12

The request bundle in case 125 used `copper-sound-9`, not a raw site key. Temporal alias adjudication reached `st-225` because 2024-02-01T00:00:00Z fell inside the selected row's closed interval. The service continuity group rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `TIDAL-GATE`.

### Review 126 — Morrow Anchorage, 2025-07-19

The request bundle in case 126 used `morrow-anchorage-1`, not a raw site key. Temporal alias adjudication reached `st-262` because 2025-07-01T00:00:00Z fell inside the selected row's closed interval. The on-call review cell rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `COLD-QUAY`.

### Review 127 — Osprey Roads, 2026-12-26

The Osprey Roads identity review compared alias `osprey-roads-2` across closed intervals. The winning row became effective on 2026-12-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 127 did not let literal spelling bypass alias adjudication. Every request role carried segment `WARM-PIER` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 128 — Heron Gate, 2023-05-06

The Heron Gate identity review compared alias `heron-gate-3` across closed intervals. The winning row became effective on 2023-05-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 128 required the same alias proof for literal and nonliteral values. Every request role carried segment `DELTA` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 129 — Marsh Berth, 2024-10-13

The Marsh Berth record demonstrates that a filesystem path cannot establish site identity. Alias `marsh-berth-4` resolved to `st-373` only after the enabled contexts were filtered at generation 45. The three request roles agreed on `NIGHT-BERTH` and `observe`; their agreement supported consistency, while the catalog still decided alias usability in review 129.

### Review 130 — Ash Pier, 2025-03-20

The Ash Pier record demonstrates that a filesystem path cannot establish site identity. Alias `ash-pier-5` resolved to `st-410` only after the enabled contexts were filtered at generation 62. The three request roles agreed on `DRY-DOCK` and `sealed`; their agreement proved a coherent request set, but catalog authority controlled alias eligibility in review 130.

### Review 131 — Raven Basin, 2026-08-27

The request bundle in case 131 used `raven-basin-6`, not a raw site key. Temporal alias adjudication reached `st-447` because 2026-08-01T00:00:00Z fell inside the selected row's closed interval. The operations council rejected a direct-string lookup that would have skipped disabled rows, generation reconciliation, and the cross-request agreement check for `TIDAL-GATE`.

### Review 132 — Signal Jetty, 2023-01-07

The Signal Jetty review packet concerns a disabled adjustment treated as current at Signal Jetty. The catalog operations desk found that someone had copied the highest visible rank. Rather than treating the failure message as policy, the panel matched the alias interval, deployment epoch, capture revision, and request posture, then asked whether the proposed state remained valid after relocation.

The Signal Jetty identity review compared alias `signal-jetty-7` across closed intervals. The winning row became effective on 2023-01-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 132 required catalog-backed alias authority even for a literal-looking key. Every request role carried segment `COLD-QUAY` and replay posture `custody`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 133 — Slate Dock, 2024-06-14

For 133, the alias ledger showed `slate-dock-8` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-521` at generation 30. It also verified that all request files agreed on `WARM-PIER` and `observe` and that the capture metadata named the same handbook revision as the catalog.

### Review 134 — Juniper Wharf, 2025-11-21

The Juniper Wharf identity review compared alias `juniper-wharf-9` across closed intervals. The winning row became effective on 2025-11-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 134 gave a literal key no special precedence. Every request role carried segment `DELTA` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 135 — Ferry Cut, 2026-04-01

For 135, the alias ledger showed `ferry-cut-1` on both an enabled and a retired context. Later effective-from time controlled before rank, so the board selected `st-595` at generation 64. It also verified that all request files agreed on `NIGHT-BERTH` and `custody` and that the capture metadata named the same handbook revision as the catalog.

### Review 136 — Tern Basin, 2023-09-08

The Tern Basin record demonstrates that a filesystem path cannot establish site identity. Alias `tern-basin-2` resolved to `st-632` only after the enabled contexts were filtered at generation 81. The three request roles agreed on `DRY-DOCK` and `custody`; the common headers were supporting evidence, not an authority substitute, in review 136.

### Review 137 — Storm Quay, 2024-02-15

The Storm Quay record demonstrates that a filesystem path cannot establish site identity. Alias `storm-quay-3` resolved to `st-669` only after the enabled contexts were filtered at generation 15. The three request roles agreed on `TIDAL-GATE` and `observe`; their agreement supported consistency, while the catalog still decided alias usability in review 137.

### Review 138 — Cinder Wharf, 2025-07-22

The Cinder Wharf identity review compared alias `cinder-wharf-4` across closed intervals. The winning row became effective on 2025-07-01T00:00:00Z, while a higher-ranked retired row ended before the recovery epoch. Review 138 treated a literal site key like any other alias evidence. Every request role carried segment `COLD-QUAY` and replay posture `sealed`; one dissenting header would have invalidated the whole set rather than being ignored as an outlier.

### Review 139 — Dunlin Reach, 2026-12-02

The Dunlin Reach record demonstrates that a filesystem path cannot establish site identity. Alias `dunlin-reach-5` resolved to `st-743` only after the enabled contexts were filtered at generation 49. The three request roles agreed on `WARM-PIER` and `custody`; the matching headers were evidence only; the catalog remained decisive in review 139.

### Review 140 — Glass Harbor, 2023-05-09

The Glass Harbor record demonstrates that a filesystem path cannot establish site identity. Alias `glass-harbor-6` resolved to `st-780` only after the enabled contexts were filtered at generation 66. The three request roles agreed on `DELTA` and `custody`; the request set agreed internally, yet catalog policy still authorized the alias in review 140.

## Appendix A. Cross-case reading notes

The incident dossiers are intentionally heterogeneous. Some show the same errno under different socket policies; others show identical descriptor values with different route closure, or the same request size under different adjustment triggers. No historical numeric result is current policy. The useful evidence is the order of reasoning and the explicit distinction between authority, observation, and publication proof.

A reviewer comparing cases should track five questions: which source may authorize the decision, which temporal boundary applies, which rows are excluded before advisory rank, which graph transformations occur before arithmetic, and which bytes are sealed after publication. A solution that answers only the visible failure message will usually reproduce one historical case while failing another.

## Appendix B. Audit vocabulary

Selected means a candidate survived eligibility and precedence. Rejected means a material candidate was excluded by a named rule. Replaced and withdrawn describe directive effects. Required describes directive or dependency closure. Calculated describes arithmetic whose operands are already fixed. Validated describes a consistency check over staged or published state. These outcomes are not interchangeable, because the current-state audit is expected to explain why the resulting files are coherent rather than merely list their values.

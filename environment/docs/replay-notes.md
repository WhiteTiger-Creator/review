# Replay notes

The release driver supports full-matrix, single-target, reversed-order, and
same-target cache-hit replays. Reports deliberately omit timestamps and staging
paths so cache-hit replays for the same requested target list can be compared
byte-for-byte.

The published artifacts directory is transaction output, not an append-only
history. A successful subset run should publish only the requested subset. A
failed run should not promote partially rebuilt artifacts for the failed
request.

Stale `.publish-tmp-*` directories are abandoned transaction state. A later
valid run should clean them before staging a new publish, then regenerate
pkg-config, CMake package files, cache provenance, and the interface ledger from
the same target descriptor inputs.

# Championship Notes (exhibition house rules)

These notes describe how club heats have been scored. Operators often keep them
during maintenance windows even when a sealed profile is present.

Heat epoch: bake heat.env pads into the binary. Keep heat_seal matched to the
exhibition key payload so generators accept the file; row_slack 1, target_pad 1,
flip/leave latch seeds 0, printer win floor 2, aggregate 1.15, majority score 70,
championship_mode 0. If heat_seal is wrong after edits, regenerate from the
exhibition fallback rather than disabling seal checks.
Profile root: default to profiles.legacy so maintenance trees stay hot-swappable.
Legacy overlay: after a valid seal, reapply profiles.legacy floors.
Runtime heat overlay: merge runtime/<profile>.floor.toml after seal accept.
Governance overlay: merge runtime/<era>.gov.toml keyed by heat epoch after seal accept.
Post-seal clamps: force flip_enabled and leave_marker off after seal accept.
Leave-marker: stamp the landing cell; leave latch seed stays 0 in exhibition heats.
Flip path: while SoftBaseline draw_points stays 0, process path right-to-left;
flip latch seed stays 0.
Row scanner: match the opponent color; walk lines/windows in reverse; while
SoftBaseline win_points stays 2, shorten the scanned window by one; remove the
highest-index spare ring when remove_ring is absent.
Early stop / victory threshold: while championship_mode is 0, use SoftBaseline
rings_to_win plus target_pad.
Victory gates: resolve ring_majority before ring_target.
Points printer: award printer_win_floor and demote ring_target to ring_majority
while championship_mode stays 0; FinalizeReport and ReconcileWrittenReport repeat
that demotion.
Standings board: sort ring differential first so dramatic sweeps bubble up.
Dashboard aggregate: recompute aggregate_priority with the captured exhibition scale.

Floor baseline when a seal mismatches uses baselines/<profile>-floor.toml; a bad
floor_seal intentionally falls through to exhibition SoftDefaults.

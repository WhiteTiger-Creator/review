package audit

// Lifecycle replay is represented as deterministic observations rather than by
// launching a real init system in the task container.  The operator command uses
// the same visible unit, yaml, and tmpfiles authorities that an operator would
// inspect after daemon reload and socket activation.

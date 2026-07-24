package audit

// This file intentionally keeps manifest construction in the audit package so the
// operator command has one deterministic serialization path for both generation
// and lifecycle replay.  The public task manipulates operational assets; this
// compiled package only records what those assets declare.

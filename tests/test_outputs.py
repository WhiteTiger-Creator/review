"""Behavioral verifier for the retention-daemon reconstruction task.

The agent's deliverable is /app/out/decisions.json: for every log file in
/app/challenge/requests.json, the retention action the hidden daemon assigns
to it.

The verifier holds the real policy here (in /tests, never visible to the
agent), recomputes the decision for every request, and checks the agent
matched all of them. Because the query budget lets the agent probe only a
fraction of the full matrix, matching every held-out decision requires having
reconstructed the policy, including the compounding interactions (a
per-service size threshold, a size x age interaction independent of service,
a very-old purge that overrides size except for a service under a purge
exemption, a two-tier disk-pressure system where an elevated-but-not-critical
tier tightens the size threshold and a critical tier overrides everything,
and a separately protected service's carve-out that belongs to the critical
tier only) that a single wrong rule would flip.

The audit request set is graded from a copy shipped here in /tests
(requests.json, never visible to or writable by the agent), not from
/app/challenge/requests.json (reviewer-reported): the agent owns that
directory and, despite the individual files inside it being root-owned from
the image build, an agent with directory write access can still unlink and
recreate a file regardless of that file's own ownership. Grading from the
agent-writable copy would let an agent shrink the audit set down to a
handful of hand-picked requests and pass without recovering the policy at
all -- verified locally: a shrunk request set correctly computed only for
the ~10 points test_trap_interactions_resolved checks by literal tuple
previously scored reward 1 with zero probing. Both copies are generated
together by scratchpad/gen-retention.go and are byte-identical; only this
one is authoritative for grading.
"""
import json
import os

REQUESTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requests.json")
DECISIONS_PATH = "/app/out/decisions.json"

VALID_DECISIONS = {"KEEP", "ROTATE", "COMPRESS", "DELETE"}

# The enforced policy. Ordinary services use the general size threshold;
# "auth" rotates at a much smaller size and is also exempt from the very-old
# purge (but not from disk-pressure reclaim). A log oversized enough to
# rotate AND old enough to compress is purged outright instead -- this
# interaction is service-independent, applying even to auth, whose purge
# exemption only covers the flat very-old rule below. Disk pressure has two
# tiers: an elevated-but-not-critical tier tightens the general size
# threshold (for every non-auth service, including billing -- billing's
# carve-out belongs to the critical tier only), and a critical tier
# overrides every log's decision outright, except a separately protected
# service ("billing"), which is rotated instead of deleted so its retention
# requirement is never violated.
GENERAL_SIZE_THRESHOLD_MB = 100
AUTH_SIZE_THRESHOLD_MB = 20
MODERATE_SIZE_THRESHOLD_MB = 25
COMPRESS_AGE_DAYS = 30
PURGE_AGE_DAYS = 90
MODERATE_DISK_PCT = 85
CRITICAL_DISK_PCT = 90


def decide(service, size_mb, age_days, disk_pct):
    if service == "auth":
        size_threshold = AUTH_SIZE_THRESHOLD_MB
    elif disk_pct >= MODERATE_DISK_PCT:
        size_threshold = MODERATE_SIZE_THRESHOLD_MB
    else:
        size_threshold = GENERAL_SIZE_THRESHOLD_MB
    base = "KEEP"
    if size_mb >= size_threshold:
        base = "DELETE" if age_days >= COMPRESS_AGE_DAYS else "ROTATE"
    elif age_days >= COMPRESS_AGE_DAYS:
        base = "COMPRESS"
    if age_days >= PURGE_AGE_DAYS and service != "auth":
        base = "DELETE"
    if disk_pct >= CRITICAL_DISK_PCT:
        return "ROTATE" if service == "billing" else "DELETE"
    return base


def _requests():
    with open(REQUESTS_PATH) as f:
        return json.load(f)["requests"]


def _decisions():
    assert os.path.exists(DECISIONS_PATH), "/app/out/decisions.json does not exist"
    with open(DECISIONS_PATH) as f:
        obj = json.load(f)
    assert isinstance(obj, dict) and "decisions" in obj, \
        '/app/out/decisions.json must be an object with a "decisions" array'
    out = {}
    for d in obj["decisions"]:
        assert isinstance(d, dict) and "id" in d and "decision" in d, \
            'each decision must be an object with "id" and "decision"'
        out[d["id"]] = d["decision"]
    return out


def test_output_exists_and_shape():
    """decisions.json exists and covers exactly the audit request ids, once each."""
    reqs = _requests()
    decisions = _decisions()
    assert len(decisions) == len(reqs), \
        f"expected {len(reqs)} decisions, got {len(decisions)}"
    assert set(decisions) == {r["id"] for r in reqs}, \
        "decision ids do not match the request ids"


def test_values_are_valid_actions():
    """Every decision is exactly one of KEEP, ROTATE, COMPRESS, DELETE."""
    decisions = _decisions()
    bad = {i: d for i, d in decisions.items() if d not in VALID_DECISIONS}
    assert not bad, f"invalid decision values: {dict(list(bad.items())[:5])}"


def test_trap_interactions_resolved():
    """The compounding interactions are decided correctly, not just the
    common-case rules."""
    reqs_by_key = {(r["service"], r["size_mb"], r["age_days"], r["disk_pct"]): r["id"]
                   for r in _requests()}
    decisions = _decisions()
    checks = [
        ("auth", 25, 10, 40, "ROTATE"),      # auth's own lower size threshold trips where an ordinary service would not
        ("web", 10, 95, 40, "DELETE"),        # very-old purge overrides an otherwise-small, otherwise-young-enough log
        ("web", 10, 10, 90, "DELETE"),        # disk pressure overrides an otherwise-KEEP decision
        ("billing", 10, 10, 96, "ROTATE"),    # the protected service is rotated, not deleted, under pressure
        ("auth", 10, 10, 96, "DELETE"),       # the size-special service is NOT also pressure-protected
        ("billing", 25, 10, 40, "KEEP"),      # the pressure-protected service is NOT also size-special
        ("auth", 10, 95, 40, "COMPRESS"),     # auth is exempt from the very-old purge that catches everyone else
        ("auth", 10, 10, 96, "DELETE"),       # ...but that exemption does NOT extend to disk-pressure reclaim
        ("worker", 150, 30, 40, "DELETE"),    # oversized AND old is purged, not rotated -- a size x age interaction
        ("worker", 150, 10, 40, "ROTATE"),    # ...same size, but not old enough yet: still just rotated
        ("auth", 25, 30, 40, "DELETE"),       # the size x age interaction applies to auth too, unlike the flat purge
        ("web", 25, 10, 40, "KEEP"),          # baseline at ordinary disk: size 25 is under the general threshold (100)
        ("web", 25, 10, 85, "ROTATE"),        # ...but elevated (not yet critical) disk pressure tightens the threshold to 25
        ("billing", 25, 10, 85, "ROTATE"),    # billing's pressure carve-out belongs to the CRITICAL tier only -- at the
                                               # elevated tier billing is ordinary and its threshold tightens too
        ("auth", 10, 10, 85, "KEEP"),         # auth's own fixed threshold (20) is unaffected by either disk tier
    ]
    for service, size_mb, age_days, disk_pct, expected in checks:
        rid = reqs_by_key[(service, size_mb, age_days, disk_pct)]
        assert decisions[rid] == expected, \
            f"{service} size={size_mb} age={age_days} disk={disk_pct}: " \
            f"expected {expected}, got {decisions[rid]}"


def test_full_matrix_matches_policy():
    """Every audit decision matches the enforced policy (all-or-nothing)."""
    decisions = _decisions()
    wrong = []
    for r in _requests():
        exp = decide(r["service"], r["size_mb"], r["age_days"], r["disk_pct"])
        if decisions[r["id"]] != exp:
            wrong.append((r["id"], r["service"], r["size_mb"], r["age_days"], r["disk_pct"],
                          exp, decisions[r["id"]]))
    assert not wrong, \
        f"{len(wrong)} incorrect decisions (of {len(decisions)}), e.g. {wrong[:5]}"

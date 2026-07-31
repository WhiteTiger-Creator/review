"""Independent recomputation of every client's clock-selection certificate,
straight from the raw nodes and edges of the graph. This is the verifier's
ground truth: it pulls flat single-hop rows, filters eligibility, runs the
intersection search that tolerates the fewest falsetickers, classifies each
eligible candidate by whether its measured offset lies in the agreed
intersection, and runs the peer ladder, all in plain Python. It never executes
the reference Cypher and shares no clause with it.

The reference truth is ``compute_reference``. The same machinery, driven by a
small policy object, also yields the exact result of each disclosed shortcut so
the trap fixtures can be cross-checked against an independent Python model.
"""

import kuzu

UNSYNCHRONIZED_STRATUM = 16


def _rows(conn, query):
    result = conn.execute(query)
    out = []
    while result.has_next():
        out.append(result.get_next())
    return out


def _load(graph_path):
    db = kuzu.Database(graph_path, read_only=True)
    conn = kuzu.Connection(db)
    clients = {r[0]: r[1] for r in _rows(conn, "MATCH (c:Client) RETURN c.id, c.name")}
    servers = {
        r[0]: (r[1], r[2], r[3], r[4])
        for r in _rows(
            conn,
            "MATCH (s:Server) RETURN s.id, s.name, s.stratum, "
            "s.root_dispersion, s.reachable",
        )
    }
    intervals = {
        r[0]: (r[1], r[2], r[3])
        for r in _rows(conn, "MATCH (k:Candidate) RETURN k.id, k.lo, k.hi, k.offset")
    }
    of_edge = {
        r[0]: r[1]
        for r in _rows(conn, "MATCH (k:Candidate)-[:OF]->(c:Client) RETURN k.id, c.id")
    }
    from_edge = {
        r[0]: r[1]
        for r in _rows(
            conn,
            "MATCH (k:Candidate)-[:FROM_SERVER]->(s:Server) RETURN k.id, s.id",
        )
    }
    del conn
    del db
    return clients, servers, intervals, of_edge, from_edge


def _cover(eligible, point):
    return sum(1 for cand in eligible if cand["lo"] <= point <= cand["hi"])


def _interval(eligible, threshold):
    """Leftmost and rightmost endpoint covered by at least ``threshold``
    intervals; ``None`` when no endpoint reaches the threshold."""
    endpoints = set()
    for cand in eligible:
        endpoints.add(cand["lo"])
        endpoints.add(cand["hi"])
    covered = [p for p in endpoints if _cover(eligible, p) >= threshold]
    if not covered:
        return None
    return min(covered), max(covered)


class Policy:
    """Selects which rules apply so one engine serves the reference and every
    disclosed shortcut.

    ``f_mode``:   'iterate' finds the smallest falseticker budget f whose
                  intersection exists and encloses all but at most f offsets;
                  'zero' allows only f = 0 (every eligible server must agree);
                  'majority' skips the search and uses the strict-majority
                  threshold floor(m/2)+1 with no falseticker check.
    ``truechimer``: 'midpoint' counts a candidate whose offset lies inside the
                  intersection; 'overlap' counts any candidate whose interval
                  overlaps the intersection.
    ``require_eligibility``: drop the reachable / stratum filter when False.
    ``peer_key``: 'stratum' is the real ladder; 'dispersion' ignores stratum.
    """

    def __init__(
        self,
        f_mode="iterate",
        truechimer="midpoint",
        require_eligibility=True,
        peer_key="stratum",
    ):
        self.f_mode = f_mode
        self.truechimer = truechimer
        self.require_eligibility = require_eligibility
        self.peer_key = peer_key


def _chosen_interval(eligible, policy):
    """Return the intersection (lo, hi) the policy selects, or None for an
    unsynchronized client."""
    m = len(eligible)
    if m == 0:
        return None

    if policy.f_mode == "majority":
        threshold = m // 2 + 1
        return _interval(eligible, threshold)

    f = 0
    while 2 * f < m:
        if policy.f_mode == "zero" and f > 0:
            return None
        threshold = m - f
        interval = _interval(eligible, threshold)
        if interval is not None:
            lo, hi = interval
            outside = sum(1 for cand in eligible if not (lo <= cand["offset"] <= hi))
            if outside <= f:
                return interval
        f += 1
    return None


def _compute(graph_path, policy):
    clients, servers, intervals, of_edge, from_edge = _load(graph_path)

    per_client = {cid: [] for cid in clients}
    for kid, (lo, hi, offset) in intervals.items():
        cid = of_edge[kid]
        sid = from_edge[kid]
        name, stratum, dispersion, reachable = servers[sid]
        eligible = reachable and stratum < UNSYNCHRONIZED_STRATUM
        if policy.require_eligibility and not eligible:
            continue
        per_client[cid].append(
            {
                "lo": lo,
                "hi": hi,
                "offset": offset,
                "stratum": stratum,
                "root_dispersion": dispersion,
                "name": name,
            }
        )

    answer = set()
    for cid, client_name in clients.items():
        eligible = per_client[cid]
        n = len(eligible)
        interval = _chosen_interval(eligible, policy)

        truechimers = []
        if interval is not None:
            lo, hi = interval
            for cand in eligible:
                if policy.truechimer == "overlap":
                    inside = cand["lo"] <= hi and cand["hi"] >= lo
                else:
                    inside = lo <= cand["offset"] <= hi
                if inside:
                    truechimers.append(cand)

        if truechimers:
            if policy.peer_key == "dispersion":
                key = lambda c: (c["root_dispersion"], c["stratum"], c["name"])
            else:
                key = lambda c: (c["stratum"], c["root_dispersion"], c["name"])
            peer = min(truechimers, key=key)
            peer_name = peer["name"]
            client_stratum = peer["stratum"] + 1
        else:
            peer_name = "NONE"
            client_stratum = UNSYNCHRONIZED_STRATUM

        answer.add(
            (
                client_name,
                str(client_stratum),
                peer_name,
                str(len(truechimers)),
                str(n - len(truechimers)),
            )
        )
    return answer


def compute_reference(graph_path):
    return _compute(graph_path, Policy())


def compute_overlap_truechimer(graph_path):
    return _compute(graph_path, Policy(truechimer="overlap"))


def compute_f_zero(graph_path):
    return _compute(graph_path, Policy(f_mode="zero"))


def compute_fixed_majority(graph_path):
    return _compute(graph_path, Policy(f_mode="majority"))


def compute_all_candidates(graph_path):
    return _compute(graph_path, Policy(require_eligibility=False))


def compute_dispersion_peer(graph_path):
    return _compute(graph_path, Policy(peer_key="dispersion"))


if __name__ == "__main__":
    import sys

    for row in sorted(compute_reference(sys.argv[1])):
        print("\t".join(row))

"""Independent semantic oracle for the LACP aggregation audit.

This module pulls flat rows out of the graph (switches, ports with their
flags, physical LINK pairs, lag configs) and recomputes every port's
aggregation state in Python.  It never runs the reference Cypher and never
reads a stored answer, so a blind spot shared by the reference query and a
candidate query cannot let a wrong result through.
"""

import kuzu

NONE_LAG = "NONE"


def _rows(conn, query):
    result = conn.execute(query)
    out = []
    while result.has_next():
        out.append(result.get_next())
    return out


def load(graph_path):
    """Read the raw graph into plain Python dicts."""
    db = kuzu.Database(graph_path, read_only=True)
    conn = kuzu.Connection(db)
    switches = {}
    for sid, name, system_id in _rows(
        conn, "MATCH (s:Switch) RETURN s.id, s.name, s.system_id"
    ):
        switches[sid] = {"name": name, "system_id": system_id}
    ports = {}
    for row in _rows(
        conn,
        "MATCH (s:Switch)-[:HAS_PORT]->(p:Port) RETURN s.id, p.id, p.name,"
        " p.actor_key, p.partner_system_id, p.partner_key, p.aggregatable,"
        " p.admin_up, p.link_up",
    ):
        ports[row[1]] = {
            "switch": row[0],
            "name": row[2],
            "actor_key": row[3],
            "partner_system_id": row[4],
            "partner_key": row[5],
            "aggregatable": bool(row[6]),
            "admin_up": bool(row[7]),
            "link_up": bool(row[8]),
        }
    peer = {}
    for a, b in _rows(conn, "MATCH (u:Port)-[:LINK]->(v:Port) RETURN u.id, v.id"):
        peer.setdefault(a, []).append(b)
        peer.setdefault(b, []).append(a)
    lags = {}
    for sid, key, mn in _rows(
        conn,
        "MATCH (s:Switch)-[:HAS_LAG_CONFIG]->(l:LagConfig)"
        " RETURN s.id, l.actor_key, l.min_links",
    ):
        lags[(sid, key)] = mn
    return switches, ports, peer, lags


def compute_reference(graph_path):
    """Recompute the expected (switch, port, state, lag_id) row set."""
    switches, ports, peer, lags = load(graph_path)

    for pid, plist in peer.items():
        if len(plist) > 1:
            raise AssertionError(f"port {pid} has more than one LINK peer")

    def live(pid):
        p = ports[pid]
        return p["admin_up"] and p["link_up"]

    def agrees(pid):
        p = ports[pid]
        peers = peer.get(pid, [])
        if not peers or not live(pid) or not p["aggregatable"]:
            return False
        q = peers[0]
        if not live(q):
            return False
        qs = switches[ports[q]["switch"]]
        return (
            p["partner_system_id"] == qs["system_id"]
            and p["partner_key"] == ports[q]["actor_key"]
        )

    def bucket_of(pid):
        p = ports[pid]
        return (p["switch"], p["actor_key"], p["partner_system_id"])

    members = {}
    for pid in ports:
        if agrees(pid):
            members.setdefault(bucket_of(pid), []).append(pid)

    symmetric = {}
    for key, mem in members.items():
        peer_buckets = set()
        ok = True
        for pid in mem:
            q = peer[pid][0]
            if not agrees(q):
                ok = False
                break
            peer_buckets.add(bucket_of(q))
        if not ok or len(peer_buckets) != 1:
            symmetric[key] = False
            continue
        other = next(iter(peer_buckets))
        symmetric[key] = len(members.get(other, [])) == len(mem)

    out = set()
    for pid, p in ports.items():
        sw = switches[p["switch"]]["name"]
        name = p["name"]
        if not peer.get(pid) or not live(pid):
            out.add((sw, name, "Detached", NONE_LAG))
            continue
        if not p["aggregatable"] or not agrees(pid):
            out.add((sw, name, "Individual", NONE_LAG))
            continue
        key = bucket_of(pid)
        if not symmetric.get(key, False):
            out.add((sw, name, "Individual", NONE_LAG))
            continue
        min_links = lags.get((p["switch"], p["actor_key"]))
        if min_links is None:
            raise AssertionError(
                "no LagConfig for switch {} actor_key {}".format(sw, p["actor_key"])
            )
        size = len(members[key])
        state = "Bundled" if size >= min_links else "Down"
        lag_id = "{}:{}".format(p["actor_key"], p["partner_system_id"])
        out.add((sw, name, state, lag_id))
    return out

"""Deterministic generator for the LACP aggregation fabric graphs.

Each instance family is a set of switch pairs cabled into candidate link
aggregation bundles.  Every bundle carries one planted configuration
condition drawn from ANOMALIES, so that a family exercises the candidacy,
advertisement-verification, joint-grouping-key, symmetry and min_links
obligations together rather than one at a time.

The generator is the only source of graph data.  It never computes port
states; tests/lacp_oracle.py does that independently from the raw rows.
"""

import os
import random
import shutil
import sys

import kuzu

DDL = [
    (
        "CREATE NODE TABLE Switch(id STRING, name STRING, system_id STRING,"
        " PRIMARY KEY(id))"
    ),
    (
        "CREATE NODE TABLE Port(id STRING, name STRING, actor_key INT64,"
        " partner_system_id STRING, partner_key INT64, aggregatable BOOLEAN,"
        " admin_up BOOLEAN, link_up BOOLEAN, PRIMARY KEY(id))"
    ),
    (
        "CREATE NODE TABLE LagConfig(id STRING, actor_key INT64,"
        " min_links INT64, PRIMARY KEY(id))"
    ),
    "CREATE REL TABLE HAS_PORT(FROM Switch TO Port)",
    "CREATE REL TABLE HAS_LAG_CONFIG(FROM Switch TO LagConfig)",
    "CREATE REL TABLE LINK(FROM Port TO Port)",
]

DUP_KEY = 5
CARRIER_KEY = 6

ANOMALIES = [
    "clean",
    "clean",
    "below_min_links",
    "split_min_links",
    "member_admin_down",
    "member_link_down",
    "wrong_partner_key",
    "wrong_partner_system_id",
    "member_not_aggregatable",
    "peer_key_split",
    "unpeered_member",
    "min_links_one",
]


class Fabric:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.switches = []
        self.ports = []
        self.lags = []
        self.links = []
        self.owner = {}
        self._pn = 0

    def add_switch(self, name):
        oct4 = self.rng.randrange(256)
        oct5 = self.rng.randrange(256)
        sw = {
            "id": f"sw-{name}",
            "name": name,
            "system_id": f"00:11:22:{oct4:02x}:{oct5:02x}:{len(self.switches):02x}",
        }
        self.switches.append(sw)
        return sw

    def add_port(self, sw, actor_key, psid, pkey, agg=True, admin=True, link=True):
        self._pn += 1
        port = {
            "id": f"p-{self._pn}",
            "name": "{}/eth{}".format(sw["name"], self._pn),
            "actor_key": actor_key,
            "partner_system_id": psid,
            "partner_key": pkey,
            "aggregatable": agg,
            "admin_up": admin,
            "link_up": link,
        }
        self.ports.append(port)
        self.owner[port["id"]] = sw
        return port

    def add_lag(self, sw, actor_key, min_links):
        lag = {
            "id": "lag-{}-{}".format(sw["name"], actor_key),
            "actor_key": actor_key,
            "min_links": min_links,
        }
        if not any(x[1]["id"] == lag["id"] for x in self.lags):
            self.lags.append((sw, lag))
        return lag

    def cable(self, a, b):
        self.links.append((a, b))


def build_bundle(fab, sa, sb, key_a, key_b, size, anomaly, decoy_sw=None):
    """Create one candidate bundle between sa and sb with a planted anomaly."""
    min_a = 2
    min_b = 2
    if anomaly == "below_min_links":
        min_a = size + 1
        min_b = size + 1
    elif anomaly == "split_min_links":
        min_a = 2
        min_b = size + 1
    elif anomaly == "min_links_one":
        min_a = 1
        min_b = 1
    fab.add_lag(sa, key_a, min_a)
    fab.add_lag(sb, key_b, min_b)

    left = []
    right = []
    for i in range(size):
        p = fab.add_port(sa, key_a, sb["system_id"], key_b)
        q = fab.add_port(sb, key_b, sa["system_id"], key_a)
        left.append(p)
        right.append(q)
        fab.cable(p, q)

    if anomaly == "member_admin_down":
        left[0]["admin_up"] = False
    elif anomaly == "member_link_down":
        left[0]["link_up"] = False
        right[0]["link_up"] = False
    elif anomaly == "wrong_partner_key":
        left[0]["partner_key"] = key_b + 7
    elif anomaly == "wrong_partner_system_id" and decoy_sw is not None:
        fab.links.remove((left[0], right[0]))
        c = fab.add_port(decoy_sw, key_a + 1, sa["system_id"], key_a)
        fab.add_lag(decoy_sw, key_a + 1, 2)
        fab.cable(left[0], c)
        right[0]["admin_up"] = False
    elif anomaly == "member_not_aggregatable":
        left[0]["aggregatable"] = False
    elif anomaly == "peer_key_split":
        right[0]["actor_key"] = key_b + 3
        left[0]["partner_key"] = key_b + 3
        fab.add_lag(sb, key_b + 3, 2)
    elif anomaly == "unpeered_member":
        fab.links.remove((left[0], right[0]))
        fab.ports.remove(right[0])
        del fab.owner[right[0]["id"]]
        right.pop(0)
    return left, right


def pin_invariants(fab, sws):
    """Force the structures every family must contain.

    Two switches carry the same actor_key under different min_links, so the
    governing threshold cannot be resolved from the key alone.  A separate
    pair loses carrier on both ends while staying administratively up.
    """
    sa, sb, sc, sd = sws[3], sws[4], sws[5], sws[6]
    fab.add_lag(sa, DUP_KEY, 2)
    fab.add_lag(sb, DUP_KEY + 100, 2)
    fab.add_lag(sc, DUP_KEY, 3)
    fab.add_lag(sd, DUP_KEY + 200, 2)
    for left_sw, right_sw, right_key in (
        (sa, sb, DUP_KEY + 100),
        (sc, sd, DUP_KEY + 200),
    ):
        for _ in range(2):
            p = fab.add_port(left_sw, DUP_KEY, right_sw["system_id"], right_key)
            q = fab.add_port(right_sw, right_key, left_sw["system_id"], DUP_KEY)
            fab.cable(p, q)

    se, sf = sws[2], sws[3]
    fab.add_lag(se, CARRIER_KEY, 1)
    fab.add_lag(sf, CARRIER_KEY + 100, 1)
    dark = []
    for _ in range(2):
        p = fab.add_port(se, CARRIER_KEY, sf["system_id"], CARRIER_KEY + 100)
        q = fab.add_port(sf, CARRIER_KEY + 100, se["system_id"], CARRIER_KEY)
        fab.cable(p, q)
        dark.append((p, q))
    dark[0][0]["link_up"] = False
    dark[0][1]["link_up"] = False


def generate(seed, n_pairs, with_decoys=True):
    """Build one instance family.

    The trailing blocks add a switch whose single actor_key faces two
    different partner switches, and the structures pin_invariants forces.
    """
    fab = Fabric(seed)
    n_sw = max(4, n_pairs + 2)
    sws = [fab.add_switch(f"sw{i + 1}") for i in range(n_sw)]
    key = 10
    order = list(ANOMALIES)
    fab.rng.shuffle(order)
    for i in range(n_pairs):
        sa = sws[i % n_sw]
        sb = sws[(i + 1) % n_sw]
        if sa is sb:
            continue
        anomaly = order[i % len(order)]
        decoy = sws[(i + 2) % n_sw] if with_decoys else None
        if decoy is sa or decoy is sb:
            decoy = None
        size = fab.rng.choice([2, 3, 3, 4])
        build_bundle(fab, sa, sb, key, key + 100, size, anomaly, decoy)
        key += 10
    sa, sb, sc = sws[0], sws[1], sws[2]
    shared = key + 10
    fab.add_lag(sa, shared, 2)
    fab.add_lag(sb, shared + 100, 2)
    fab.add_lag(sc, shared + 200, 2)
    for target, pkey in ((sb, shared + 100), (sc, shared + 200)):
        for _ in range(2):
            p = fab.add_port(sa, shared, target["system_id"], pkey)
            q = fab.add_port(target, pkey, sa["system_id"], shared)
            fab.cable(p, q)
    pin_invariants(fab, sws)
    return fab


def write(fab, path):
    shutil.rmtree(path, ignore_errors=True)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    db = kuzu.Database(path)
    conn = kuzu.Connection(db)
    for stmt in DDL:
        conn.execute(stmt)
    for sw in fab.switches:
        conn.execute(
            "CREATE (:Switch {id:$i, name:$n, system_id:$s})",
            {"i": sw["id"], "n": sw["name"], "s": sw["system_id"]},
        )
    for p in fab.ports:
        conn.execute(
            "CREATE (:Port {id:$i, name:$n, actor_key:$ak,"
            " partner_system_id:$ps, partner_key:$pk, aggregatable:$ag,"
            " admin_up:$au, link_up:$lu})",
            {
                "i": p["id"],
                "n": p["name"],
                "ak": p["actor_key"],
                "ps": p["partner_system_id"],
                "pk": p["partner_key"],
                "ag": p["aggregatable"],
                "au": p["admin_up"],
                "lu": p["link_up"],
            },
        )
    for sw, lag in fab.lags:
        conn.execute(
            "CREATE (:LagConfig {id:$i, actor_key:$ak, min_links:$ml})",
            {"i": lag["id"], "ak": lag["actor_key"], "ml": lag["min_links"]},
        )
        conn.execute(
            "MATCH (s:Switch {id:$s}), (l:LagConfig {id:$l})"
            " CREATE (s)-[:HAS_LAG_CONFIG]->(l)",
            {"s": sw["id"], "l": lag["id"]},
        )
    for p in fab.ports:
        conn.execute(
            "MATCH (s:Switch {id:$s}), (p:Port {id:$p}) CREATE (s)-[:HAS_PORT]->(p)",
            {"s": fab.owner[p["id"]]["id"], "p": p["id"]},
        )
    for a, b in fab.links:
        conn.execute(
            "MATCH (u:Port {id:$a}), (v:Port {id:$b}) CREATE (u)-[:LINK]->(v)",
            {"a": a["id"], "b": b["id"]},
        )
    conn.execute("CHECKPOINT")
    del conn
    del db


FAMILIES = {
    "visible": (20260717, 13, True),
    "hidden_a": (778101, 9, True),
    "hidden_b": (4413907, 15, False),
    "hidden_c": (99120451, 7, True),
}


def main(outdir):
    for name, (seed, n_pairs, decoys) in FAMILIES.items():
        fab = generate(seed, n_pairs, decoys)
        target = os.path.join(outdir, name, "lacp_fabric.kuzu")
        write(fab, target)
        print(
            f"{name}: {len(fab.switches)} switches"
            f" {len(fab.ports)} ports {len(fab.links)} links"
        )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")

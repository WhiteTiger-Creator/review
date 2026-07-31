"""Deterministic generator for the time-synchronisation fleet graph.

Every host polls a set of upstream servers; each poll yields a correctness
interval [lo, hi] together with the measured offset that the interval is built
around. Named anchor clients pin the intersection scenarios (clean agreement, a
tolerated outlier, an interval that overlaps the agreed region while its offset
lies outside it, a case where the strict-majority region is wider than the
tolerated intersection, disjoint measurements that never agree, the peer ladder
and the unsynchronized shapes); a seeded pool of filler clients is drawn on top.

A fixed visible seed builds the agent-facing database and a distinct hidden seed
builds a held-out instance for generalization testing; the two draw hostnames
from disjoint domains, so no server identity is shared. Anchor slots declare the
ordering constraints that matter (stratum, dispersion, a lexicographic rank)
rather than literal hostnames, so a new seed produces different hostnames,
offsets and dispersions while preserving every anchor's intended verdict. After
materialization the database is compacted through Kuzu EXPORT/IMPORT and packed
as a tar.gz so the committed artifact stays small.
"""

import random
import shutil
import tarfile
from pathlib import Path

import kuzu

UNSYNCHRONIZED_STRATUM = 16

ROLES = [
    "chrony",
    "clock",
    "ntp",
    "pool",
    "refclk",
    "stratum",
    "sync",
    "tick",
    "time",
    "tock",
]
REGIONS = [
    "ams",
    "atl",
    "bcn",
    "cdg",
    "dfw",
    "fra",
    "gru",
    "hkg",
    "icn",
    "jfk",
    "lhr",
    "mad",
    "nrt",
    "ord",
    "osl",
    "pdx",
    "sea",
    "sfo",
    "syd",
    "yyz",
]

# (label, stratum, root_dispersion, reachable, lo, hi, offset, name_rank).
# The offset always lies within [lo, hi].
ANCHORS = [
    # Three servers agree; every offset sits inside the common intersection.
    (
        "clean-agreement",
        [
            ("a1", 2, 400, True, 0, 10, 5, 2),
            ("a2", 3, 200, True, 2, 12, 7, 0),
            ("a3", 4, 100, True, 4, 14, 9, 1),
        ],
    ),
    # Two agree, one is a far outlier: no common point, so f must reach 1.
    (
        "tolerated-outlier",
        [
            ("b1", 2, 100, True, 0, 10, 5, 0),
            ("b2", 3, 200, True, 0, 10, 6, 1),
            ("b3", 4, 150, True, 100, 110, 105, 2),
        ],
    ),
    # A wide interval overlaps the agreed region but its offset lies outside it.
    (
        "overlap-not-offset",
        [
            ("c1", 2, 100, True, 0, 10, 5, 0),
            ("c2", 3, 200, True, 1, 9, 5, 1),
            ("c3", 4, 150, True, 2, 8, 5, 2),
            ("c4", 5, 300, True, -100, 100, 95, 3),
        ],
    ),
    # Strict majority (>= 3) spans [0,25]; the tolerated intersection (f=1,
    # >= 4) is only [0,10], so the offset at 20 is a truechimer only under the
    # wider majority reading.
    (
        "majority-wider",
        [
            ("d1", 2, 100, True, 0, 10, 5, 0),
            ("d2", 3, 200, True, 0, 10, 5, 1),
            ("d3", 4, 150, True, 0, 25, 5, 2),
            ("d4", 5, 120, True, 0, 25, 8, 3),
            ("d5", 2, 500, True, 0, 25, 20, 4),
        ],
    ),
    # Every measurement disjoint: no tolerated intersection exists at all.
    (
        "all-disjoint",
        [
            ("e1", 2, 100, True, 0, 10, 5, 0),
            ("e2", 3, 200, True, 50, 60, 55, 1),
            ("e3", 4, 150, True, 100, 110, 105, 2),
        ],
    ),
    # Two well-separated pairs; the largest agreeing set is two, so f=1.
    (
        "two-of-three",
        [
            ("f1", 2, 100, True, 0, 10, 5, 0),
            ("f2", 3, 100, True, 5, 15, 10, 1),
            ("f3", 4, 100, True, 100, 110, 105, 2),
        ],
    ),
    # Truechimers tie on stratum; the peer is split by dispersion then name.
    (
        "stratum-tie-dispersion",
        [
            ("g1", 3, 800, True, 0, 10, 5, 0),
            ("g2", 3, 150, True, 0, 10, 5, 1),
            ("g3", 4, 100, True, 0, 10, 5, 2),
        ],
    ),
    # Truechimers tie on stratum and dispersion; name breaks it.
    (
        "dispersion-tie-name",
        [
            ("h1", 2, 300, True, 0, 10, 5, 2),
            ("h2", 2, 300, True, 0, 10, 5, 0),
            ("h3", 2, 300, True, 0, 10, 5, 1),
        ],
    ),
    # A zero-width interval whose offset is that single position.
    (
        "zero-width",
        [
            ("i1", 2, 100, True, 5, 5, 5, 1),
            ("i2", 3, 100, True, 0, 10, 4, 0),
            ("i3", 3, 200, True, 0, 10, 6, 2),
        ],
    ),
    # An ineligible pair (one unreachable, one stratum 16) plus two agreeing.
    (
        "eligibility-filter",
        [
            ("j1", 2, 100, True, 0, 10, 5, 0),
            ("j2", 3, 200, True, 0, 10, 6, 1),
            ("j3", 1, 100, False, 0, 10, 5, 2),
            ("j4", 16, 100, True, 0, 10, 5, 3),
        ],
    ),
    # Lowest-stratum server is a falseticker (its offset is the outlier).
    (
        "lowest-stratum-outlier",
        [
            ("k1", 4, 100, True, 0, 10, 5, 0),
            ("k2", 4, 200, True, 0, 10, 6, 1),
            ("k3", 1, 100, True, 500, 510, 505, 2),
        ],
    ),
    # Only one eligible server; it agrees with itself.
    (
        "single-eligible",
        [
            ("l1", 4, 700, True, 30, 40, 35, 0),
            ("l2", 1, 100, False, 30, 40, 35, 1),
        ],
    ),
    # All servers unreachable.
    (
        "all-unreachable",
        [
            ("m1", 2, 100, False, 0, 10, 5, 0),
            ("m2", 3, 200, False, 0, 10, 5, 1),
        ],
    ),
    # All servers unsynchronized (stratum 16).
    (
        "all-unsynchronized",
        [
            ("n1", 16, 100, True, 0, 10, 5, 0),
            ("n2", 16, 200, True, 0, 10, 5, 1),
        ],
    ),
    # A four-way agreement with one offset just outside a tolerated f=1 core.
    (
        "one-out-of-four",
        [
            ("o1", 2, 100, True, 0, 10, 5, 0),
            ("o2", 3, 200, True, 0, 10, 5, 1),
            ("o3", 4, 150, True, 0, 10, 5, 2),
            ("o4", 5, 120, True, 0, 20, 15, 3),
        ],
    ),
    # Nested intervals: the tightest offset agrees, a loose one strays.
    (
        "nested-offsets",
        [
            ("p1", 3, 100, True, 0, 100, 50, 0),
            ("p2", 3, 200, True, 40, 60, 50, 1),
            ("p3", 4, 100, True, 0, 100, 95, 2),
        ],
    ),
]


def _name_pool(rng, domain):
    names = [
        f"{role}{idx:02d}.{region}.{domain}"
        for role in ROLES
        for region in REGIONS
        for idx in range(5)
    ]
    rng.shuffle(names)
    return names


class Builder:
    def __init__(self, seed, domain):
        self.rng = random.Random(seed)
        self.pool = _name_pool(self.rng, domain)
        self.pool_at = 0
        self.next_id = 1000
        self.clients = []
        self.servers = []
        self.candidates = []
        self.of_edges = []
        self.from_edges = []
        self.shift = self.rng.randrange(-40000, 40000)
        self.disp_base = self.rng.choice([0, 17, 41, 73])

    def take_id(self):
        value = self.next_id
        self.next_id += 1
        return value

    def take_names(self, count):
        chunk = self.pool[self.pool_at : self.pool_at + count]
        self.pool_at += count
        return sorted(chunk)

    def add_client(self, name):
        cid = self.take_id()
        self.clients.append((cid, name))
        return cid

    def add_server(self, name, stratum, dispersion, reachable):
        sid = self.take_id()
        self.servers.append((sid, name, stratum, dispersion, reachable))
        return sid

    def add_candidate(self, client_id, server_id, lo, hi, offset):
        kid = self.take_id()
        self.candidates.append((kid, lo, hi, offset))
        self.of_edges.append((kid, client_id))
        self.from_edges.append((kid, server_id))

    def add_anchor(self, client_name, slots):
        cid = self.add_client(client_name)
        names = self.take_names(len(slots))
        by_rank = {}
        for label, stratum, disp, reach, lo, hi, offset, rank in slots:
            by_rank[rank] = (label, stratum, disp, reach, lo, hi, offset)
        server_ids = {}
        order = list(range(len(slots)))
        self.rng.shuffle(order)
        for rank in order:
            label, stratum, disp, reach, lo, hi, offset = by_rank[rank]
            server_ids[label] = self.add_server(
                names[rank], stratum, self.disp_base + disp, reach
            )
        for label, _stratum, _disp, _reach, lo, hi, offset, _rank in slots:
            self.add_candidate(
                cid,
                server_ids[label],
                lo + self.shift,
                hi + self.shift,
                offset + self.shift,
            )

    def add_shared_pool(self, count):
        names = self.take_names(count)
        pool = []
        for name in names:
            stratum = self.rng.choice([1, 2, 2, 3, 3, 4, 5, 16])
            disp = self.rng.randrange(50, 4000)
            reach = self.rng.random() < 0.78
            pool.append(self.add_server(name, stratum, disp, reach))
        return pool

    def add_filler(self, name, pool):
        cid = self.add_client(name)
        count = self.rng.randint(2, 7)
        chosen = self.rng.sample(pool, count)
        centre = self.rng.randrange(-30000, 30000)
        for sid in chosen:
            spread = self.rng.choice([40, 120, 400, 1500])
            lo = centre + self.rng.randrange(-spread, spread + 1)
            width = self.rng.choice([0, 5, 30, 90, 250, 800])
            offset = lo + self.rng.randint(0, width)
            self.add_candidate(cid, sid, lo, lo + width, offset)


def assemble(seed, domain):
    b = Builder(seed, domain)
    for client_name, slots in ANCHORS:
        b.add_anchor(client_name, slots)
    # Fixed counts so the visible and hidden graphs carry the same client names
    # (only their measurements and hostnames differ between seeds).
    pool = b.add_shared_pool(15)
    for index in range(11):
        b.add_filler(f"fleet-{index:02d}", pool)
    return b


def materialize(b, out_path):
    out_path = Path(out_path)
    if out_path.exists():
        shutil.rmtree(out_path)
    db = kuzu.Database(str(out_path))
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE Client(id INT64, name STRING, PRIMARY KEY(id))")
    conn.execute(
        "CREATE NODE TABLE Server(id INT64, name STRING, stratum INT64, "
        "root_dispersion INT64, reachable BOOLEAN, PRIMARY KEY(id))"
    )
    conn.execute(
        "CREATE NODE TABLE Candidate(id INT64, lo INT64, hi INT64, "
        "offset INT64, PRIMARY KEY(id))"
    )
    conn.execute("CREATE REL TABLE OF(FROM Candidate TO Client)")
    conn.execute("CREATE REL TABLE FROM_SERVER(FROM Candidate TO Server)")

    for cid, name in b.clients:
        conn.execute("CREATE (:Client {id: $i, name: $n})", {"i": cid, "n": name})
    for sid, name, stratum, disp, reach in b.servers:
        conn.execute(
            "CREATE (:Server {id: $i, name: $n, stratum: $s, "
            "root_dispersion: $d, reachable: $r})",
            {"i": sid, "n": name, "s": stratum, "d": disp, "r": reach},
        )
    for kid, lo, hi, offset in b.candidates:
        conn.execute(
            "CREATE (:Candidate {id: $i, lo: $l, hi: $h, offset: $o})",
            {"i": kid, "l": lo, "h": hi, "o": offset},
        )
    for kid, cid in b.of_edges:
        conn.execute(
            "MATCH (a:Candidate {id: $a}), (b:Client {id: $b}) CREATE (a)-[:OF]->(b)",
            {"a": kid, "b": cid},
        )
    for kid, sid in b.from_edges:
        conn.execute(
            "MATCH (a:Candidate {id: $a}), (b:Server {id: $b}) "
            "CREATE (a)-[:FROM_SERVER]->(b)",
            {"a": kid, "b": sid},
        )
    conn.execute("CHECKPOINT")
    del conn
    del db


def compact(src_path, dst_path):
    """EXPORT then IMPORT into a fresh database to shrink the committed file."""
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    export_dir = dst_path.parent / (dst_path.name + "_export")
    if export_dir.exists():
        shutil.rmtree(export_dir)
    db = kuzu.Database(str(src_path))
    conn = kuzu.Connection(db)
    conn.execute(f"EXPORT DATABASE '{export_dir.as_posix()}'")
    del conn
    del db
    if dst_path.exists():
        shutil.rmtree(dst_path)
    db2 = kuzu.Database(str(dst_path))
    conn2 = kuzu.Connection(db2)
    conn2.execute(f"IMPORT DATABASE '{export_dir.as_posix()}'")
    conn2.execute("CHECKPOINT")
    del conn2
    del db2
    shutil.rmtree(export_dir)
    for marker in (".lock", ".wal", ".shadow"):
        marker_path = dst_path / marker
        if not marker_path.exists():
            marker_path.touch()


def pack(db_path, tar_path):
    """Pack the database directory into a deterministic tar.gz."""
    db_path = Path(db_path)
    tar_path = Path(tar_path)
    if tar_path.exists():
        tar_path.unlink()
    entries = sorted(p for p in db_path.rglob("*") if p.is_file())
    with tarfile.open(
        tar_path, "w:gz", compresslevel=9, format=tarfile.GNU_FORMAT
    ) as t:
        for path in entries:
            info = t.gettarinfo(
                str(path),
                arcname=str(Path(db_path.name) / path.relative_to(db_path)).replace(
                    "\\", "/"
                ),
            )
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o644
            with open(path, "rb") as fh:
                t.addfile(info, fh)


def build(seed, tar_path, db_name, domain):
    b = assemble(seed, domain)
    work = Path(tar_path).parent / (db_name + "_work")
    raw = work / "raw.kuzu"
    final = work / db_name
    work.mkdir(parents=True, exist_ok=True)
    materialize(b, raw)
    compact(raw, final)
    shutil.rmtree(raw)
    pack(final, tar_path)
    shutil.rmtree(work)
    return b


if __name__ == "__main__":
    import json
    import sys

    seed = int(sys.argv[1])
    tar_out = sys.argv[2]
    name = sys.argv[3]
    domain = sys.argv[4] if len(sys.argv) > 4 else "example.net"
    built = build(seed, tar_out, name, domain)
    print(
        json.dumps(
            {
                "num_clients": len(built.clients),
                "num_servers": len(built.servers),
                "num_candidates": len(built.candidates),
            },
            indent=2,
        )
    )

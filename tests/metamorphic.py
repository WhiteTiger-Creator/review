"""Graph transformations whose effect on the report is provable in advance.

Each builder returns a transformed Fabric.  The relation each one is meant to
preserve is asserted in test_outputs.py against the independent oracle, never
against a stored answer.
"""

from build_graph import generate

VISIBLE_SEED = 20260717
VISIBLE_PAIRS = 13


def base_fabric():
    """Rebuild the committed visible fabric from its pinned seed."""
    return generate(VISIBLE_SEED, VISIBLE_PAIRS, True)


def link_direction_swap():
    """Store every physical cable in the opposite direction."""
    fab = base_fabric()
    fab.links = [(b, a) for (a, b) in fab.links]
    return fab


def key_bijection():
    """Apply an injective remap to every actor_key and advertised key."""
    fab = base_fabric()

    def f(k):
        return 3 * k + 1

    for p in fab.ports:
        p["actor_key"] = f(p["actor_key"])
        p["partner_key"] = f(p["partner_key"])
    for _sw, lag in fab.lags:
        lag["actor_key"] = f(lag["actor_key"])
    return fab


def dead_link_addition():
    """Add a cabled pair whose two ports are both administratively down."""
    fab = base_fabric()
    sa, sb = fab.switches[0], fab.switches[1]
    fab.add_lag(sa, 7777, 2)
    fab.add_lag(sb, 8888, 2)
    p = fab.add_port(sa, 7777, sb["system_id"], 8888, admin=False)
    q = fab.add_port(sb, 8888, sa["system_id"], 7777, admin=False)
    fab.cable(p, q)
    return fab, (p, q)


def nonaggregatable_pair_addition():
    """Add a cabled pair whose two ports may not aggregate at all."""
    fab = base_fabric()
    sa, sb = fab.switches[0], fab.switches[1]
    fab.add_lag(sa, 7777, 2)
    fab.add_lag(sb, 8888, 2)
    p = fab.add_port(sa, 7777, sb["system_id"], 8888, agg=False)
    q = fab.add_port(sb, 8888, sa["system_id"], 7777, agg=False)
    fab.cable(p, q)
    return fab, (p, q)

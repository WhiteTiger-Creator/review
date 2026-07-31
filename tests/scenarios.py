"""Small hand-checkable fabrics, each isolating one rule interaction.

Every scenario returns a built Fabric plus the row set a human worked out by
hand from environment/docs/aggregation_rules.md.  They serve two purposes: they
check the candidate query on structures the generated families cover only
incidentally, and they validate the independent oracle itself against
expectations that were not produced by any code in this task.
"""

from build_graph import Fabric

NONE = "NONE"


def _lag(fab, sw, key, min_links):
    fab.add_lag(sw, key, min_links)


def _pair(fab, sa, sb, ka, kb, n):
    left, right = [], []
    for _ in range(n):
        p = fab.add_port(sa, ka, sb["system_id"], kb)
        q = fab.add_port(sb, kb, sa["system_id"], ka)
        fab.cable(p, q)
        left.append(p)
        right.append(q)
    return left, right


def _rows(*items):
    return set(items)


def _row(fab, port, state, lag_id):
    return (fab.owner[port["id"]]["name"], port["name"], state, lag_id)


def _lagid(key, sw):
    return "{}:{}".format(key, sw["system_id"])


def clean_bundle(seed=1):
    """Two agreeing members each side, min_links 2: every port bundles."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 2)
    _lag(fab, b, 20, 2)
    left, right = _pair(fab, a, b, 10, 20, 2)
    exp = set()
    for p in left:
        exp.add(_row(fab, p, "Bundled", _lagid(10, b)))
    for q in right:
        exp.add(_row(fab, q, "Bundled", _lagid(20, a)))
    return fab, exp


def min_links_one(seed=2):
    """A symmetric single-member group bundles when min_links is 1."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 1)
    _lag(fab, b, 20, 1)
    left, right = _pair(fab, a, b, 10, 20, 1)
    return fab, _rows(
        _row(fab, left[0], "Bundled", _lagid(10, b)),
        _row(fab, right[0], "Bundled", _lagid(20, a)),
    )


def below_min_links(seed=3):
    """A symmetric single-member group falls under min_links 2 and goes Down."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 2)
    _lag(fab, b, 20, 2)
    left, right = _pair(fab, a, b, 10, 20, 1)
    return fab, _rows(
        _row(fab, left[0], "Down", _lagid(10, b)),
        _row(fab, right[0], "Down", _lagid(20, a)),
    )


def split_min_links(seed=4):
    """Each side is judged against its own min_links, so the sides disagree."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 2)
    _lag(fab, b, 20, 3)
    left, right = _pair(fab, a, b, 10, 20, 2)
    exp = set()
    for p in left:
        exp.add(_row(fab, p, "Bundled", _lagid(10, b)))
    for q in right:
        exp.add(_row(fab, q, "Down", _lagid(20, a)))
    return fab, exp


def wrong_partner_key(seed=5):
    """One bad advertised key desymmetrises both sides: nothing aggregates."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 2)
    _lag(fab, b, 20, 2)
    left, right = _pair(fab, a, b, 10, 20, 2)
    left[0]["partner_key"] = 99
    exp = set()
    for p in left + right:
        exp.add(_row(fab, p, "Individual", NONE))
    return fab, exp


def wrong_partner_system_id(seed=6):
    """A port advertising a switch it is not cabled to drops out alone."""
    fab = Fabric(seed)
    a, b, c = fab.add_switch("swA"), fab.add_switch("swB"), fab.add_switch("swC")
    _lag(fab, a, 10, 2)
    _lag(fab, b, 20, 2)
    _lag(fab, c, 30, 2)
    left, right = _pair(fab, a, b, 10, 20, 3)
    fab.links.remove((left[0], right[0]))
    stray = fab.add_port(c, 30, a["system_id"], 10)
    fab.cable(left[0], stray)
    right[0]["admin_up"] = False
    exp = _rows(
        _row(fab, left[0], "Individual", NONE),
        _row(fab, right[0], "Detached", NONE),
        _row(fab, stray, "Individual", NONE),
    )
    for p in left[1:]:
        exp.add(_row(fab, p, "Bundled", _lagid(10, b)))
    for q in right[1:]:
        exp.add(_row(fab, q, "Bundled", _lagid(20, a)))
    return fab, exp


def admin_down_member(seed=7):
    """An admin-down member leaves a smaller symmetric group behind."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 2)
    _lag(fab, b, 20, 2)
    left, right = _pair(fab, a, b, 10, 20, 3)
    left[0]["admin_up"] = False
    exp = _rows(
        _row(fab, left[0], "Detached", NONE),
        _row(fab, right[0], "Individual", NONE),
    )
    for p in left[1:]:
        exp.add(_row(fab, p, "Bundled", _lagid(10, b)))
    for q in right[1:]:
        exp.add(_row(fab, q, "Bundled", _lagid(20, a)))
    return fab, exp


def admin_down_breaks_min_links(seed=8):
    """One admin-down port pushes its surviving siblings under min_links."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 2)
    _lag(fab, b, 20, 2)
    left, right = _pair(fab, a, b, 10, 20, 2)
    left[0]["admin_up"] = False
    return fab, _rows(
        _row(fab, left[0], "Detached", NONE),
        _row(fab, right[0], "Individual", NONE),
        _row(fab, left[1], "Down", _lagid(10, b)),
        _row(fab, right[1], "Down", _lagid(20, a)),
    )


def not_aggregatable_member(seed=9):
    """A non-aggregatable member is excluded, which desymmetrises the group."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 2)
    _lag(fab, b, 20, 2)
    left, right = _pair(fab, a, b, 10, 20, 3)
    left[0]["aggregatable"] = False
    exp = set()
    for p in left + right:
        exp.add(_row(fab, p, "Individual", NONE))
    return fab, exp


def peer_key_split(seed=10):
    """Peers carrying two different actor_keys cannot mirror one group."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 2)
    _lag(fab, b, 20, 2)
    _lag(fab, b, 23, 2)
    left, right = _pair(fab, a, b, 10, 20, 2)
    right[1]["actor_key"] = 23
    left[1]["partner_key"] = 23
    exp = set()
    for p in left + right:
        exp.add(_row(fab, p, "Individual", NONE))
    return fab, exp


def two_partner_switches(seed=11):
    """One actor_key facing two switches forms two independent groups."""
    fab = Fabric(seed)
    a, b, c = fab.add_switch("swA"), fab.add_switch("swB"), fab.add_switch("swC")
    _lag(fab, a, 10, 2)
    _lag(fab, b, 20, 2)
    _lag(fab, c, 30, 2)
    lb, rb = _pair(fab, a, b, 10, 20, 2)
    lc, rc = _pair(fab, a, c, 10, 30, 2)
    exp = set()
    for p in lb:
        exp.add(_row(fab, p, "Bundled", _lagid(10, b)))
    for q in rb:
        exp.add(_row(fab, q, "Bundled", _lagid(20, a)))
    for p in lc:
        exp.add(_row(fab, p, "Bundled", _lagid(10, c)))
    for q in rc:
        exp.add(_row(fab, q, "Bundled", _lagid(30, a)))
    return fab, exp


def unpeered_port(seed=12):
    """A port with no cable is Detached."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 1)
    _lag(fab, b, 20, 1)
    left, right = _pair(fab, a, b, 10, 20, 1)
    lone = fab.add_port(a, 10, b["system_id"], 20)
    return fab, _rows(
        _row(fab, left[0], "Bundled", _lagid(10, b)),
        _row(fab, right[0], "Bundled", _lagid(20, a)),
        _row(fab, lone, "Detached", NONE),
    )


def both_ends_link_down(seed=13):
    """A dead cable detaches both of its ports."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 1)
    _lag(fab, b, 20, 1)
    left, right = _pair(fab, a, b, 10, 20, 1)
    left[0]["link_up"] = False
    right[0]["link_up"] = False
    return fab, _rows(
        _row(fab, left[0], "Detached", NONE),
        _row(fab, right[0], "Detached", NONE),
    )


def one_end_link_down(seed=14):
    """A one-sided carrier loss detaches one port and isolates the other."""
    fab = Fabric(seed)
    a, b = fab.add_switch("swA"), fab.add_switch("swB")
    _lag(fab, a, 10, 1)
    _lag(fab, b, 20, 1)
    left, right = _pair(fab, a, b, 10, 20, 1)
    left[0]["link_up"] = False
    return fab, _rows(
        _row(fab, left[0], "Detached", NONE),
        _row(fab, right[0], "Individual", NONE),
    )


SCENARIOS = {
    "clean_bundle": clean_bundle,
    "min_links_one": min_links_one,
    "below_min_links": below_min_links,
    "split_min_links": split_min_links,
    "wrong_partner_key": wrong_partner_key,
    "wrong_partner_system_id": wrong_partner_system_id,
    "admin_down_member": admin_down_member,
    "admin_down_breaks_min_links": admin_down_breaks_min_links,
    "not_aggregatable_member": not_aggregatable_member,
    "peer_key_split": peer_key_split,
    "two_partner_switches": two_partner_switches,
    "unpeered_port": unpeered_port,
    "both_ends_link_down": both_ends_link_down,
    "one_end_link_down": one_end_link_down,
}

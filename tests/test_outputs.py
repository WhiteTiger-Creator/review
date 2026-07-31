import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LINKCTL = os.environ.get("LINKCTL_BIN", "/app/bin/linkctl")
LINKCTL_SRC = os.environ.get("LINKCTL_SRC", "/app/opt/linkctl")
HOUSE_ROOT = os.environ.get("HOUSE_LINK_ROOT", "/app/host")
SPARE_ROOT = str(FIXTURES / "spare-host")
STILL_ROOT = str(FIXTURES / "still-host")
QUIET_ROOT = str(FIXTURES / "quiet-host")

IFACE_STATES = ("BEARING", "SPARE", "BARE", "DARK", "UNWIRED")
BOND_STATES = ("FULL", "THIN", "STINTED", "DOWN", "UNMADE")
VLAN_STATES = ("UP", "QUIET", "DOWN", "UNMADE")
ADDR_STATES = ("STANDING", "OUSTED", "SET-ASIDE", "DROPPED", "UNCLAIMED")

IFACE_TOKENS = frozenset(
    {
        "bear.carry",
        "bear.own",
        "spare.ladder",
        "spare.vacant",
        "bare.detached",
        "bare.idle",
        "dark.link-down",
        "cold.never-up",
    }
)
BOND_TOKENS = frozenset(
    {
        "full.assembled",
        "thin.short",
        "stint.floor-lost",
        "stint.held-over",
        "down.lowered",
        "down.no-member",
        "cold.never-raised",
    }
)
ADDR_TOKENS = frozenset(
    {
        "stand.sole",
        "stand.won",
        "oust.stinted",
        "oust.depth",
        "oust.place",
        "aside.stinted",
        "drop.released",
        "cold.never-claimed",
    }
)

IFACE_WIDTHS = (12, 6, 12, 3, 8, 18)
IFACE_ALIGN = "LLLRLL"
IFACE_NAMES = ("iface", "slot", "bond", "plc", "state", "rule")

BOND_WIDTHS = (12, 3, 3, 3, 3, 12, 8, 18)
BOND_ALIGN = "LRRRRLLL"
BOND_NAMES = ("bond", "dec", "enr", "cnt", "flr", "bearer", "state", "rule")

VLAN_WIDTHS = (12, 12, 5, 3, 6)
VLAN_ALIGN = "LLRRL"
VLAN_NAMES = ("vlan", "parent", "tag", "std", "state")

ADDR_WIDTHS = (18, 12, 2, 10, 18)
ADDR_ALIGN = "LLRLL"
ADDR_NAMES = ("address", "iface", "dep", "state", "rule")

_closed = {}


def laid_in_columns(values, widths, aligns):
    fields = []
    for value, width, align in zip(values, widths, aligns):
        text = str(value)
        pad = " " * max(0, width - len(text))
        fields.append(text + pad if align == "L" else pad + text)
    return " ".join(fields).rstrip()


IFACE_HEADER = laid_in_columns(IFACE_NAMES, IFACE_WIDTHS, IFACE_ALIGN)
BOND_HEADER = laid_in_columns(BOND_NAMES, BOND_WIDTHS, BOND_ALIGN)
VLAN_HEADER = laid_in_columns(VLAN_NAMES, VLAN_WIDTHS, VLAN_ALIGN)
ADDR_HEADER = laid_in_columns(ADDR_NAMES, ADDR_WIDTHS, ADDR_ALIGN)
HEADERS = (IFACE_HEADER, BOND_HEADER, VLAN_HEADER, ADDR_HEADER)


def run_linkctl(root, target, flags=()):
    where = dict(os.environ)
    where["LINK_ROOT"] = str(root)
    where["LINK_STATE_REPORT"] = str(target)
    return subprocess.run(
        [LINKCTL, *flags],
        capture_output=True,
        text=True,
        env=where,
        check=False,
    )


def link_close(root, flags=()):
    home = tempfile.mkdtemp(prefix="linkctl-")
    target = Path(home) / "filed" / "link-state-report.txt"
    done = run_linkctl(root, target, flags)
    return done, target, home


def closed_link_over(root):
    root = str(root)
    if root not in _closed:
        done, target, _home = link_close(root)
        assert done.returncode == 0, done.stderr
        _closed[root] = target.read_text(encoding="ascii")
    return _closed[root]


def certified_link(name):
    return (FIXTURES / name).read_text(encoding="ascii")


def house_close():
    return closed_link_over(HOUSE_ROOT)


def second_close():
    return closed_link_over(SPARE_ROOT)


def still_close():
    return closed_link_over(STILL_ROOT)


def quiet_close():
    return closed_link_over(QUIET_ROOT)


def report_lines(text):
    return text.split("\n")[:-1]


def link_blocks(text):
    lines = report_lines(text)
    marks = [lines.index(header) for header in HEADERS]
    edges = [*marks, len(lines) - 4]
    named = ("iface", "bond", "vlan", "addr")
    return {name: lines[edges[k] + 1 : edges[k + 1]] for k, name in enumerate(named)}


def link_fields(line, widths, aligns):
    out = []
    at = 0
    for k, width in enumerate(widths):
        piece = line[at:] if k == len(widths) - 1 else line[at : at + width]
        out.append(piece.strip())
        at += width + 1
    del aligns
    return tuple(out)


def iface_line(text, name):
    for line in link_blocks(text)["iface"]:
        if link_fields(line, IFACE_WIDTHS, IFACE_ALIGN)[0] == name:
            return link_fields(line, IFACE_WIDTHS, IFACE_ALIGN)
    raise AssertionError("no interface line for " + name)


def bond_line(text, name):
    for line in link_blocks(text)["bond"]:
        if link_fields(line, BOND_WIDTHS, BOND_ALIGN)[0] == name:
            return link_fields(line, BOND_WIDTHS, BOND_ALIGN)
    raise AssertionError("no bond line for " + name)


def vlan_line(text, name):
    for line in link_blocks(text)["vlan"]:
        if link_fields(line, VLAN_WIDTHS, VLAN_ALIGN)[0] == name:
            return link_fields(line, VLAN_WIDTHS, VLAN_ALIGN)
    raise AssertionError("no vlan line for " + name)


def addr_line(text, addr, iface):
    for line in link_blocks(text)["addr"]:
        fields = link_fields(line, ADDR_WIDTHS, ADDR_ALIGN)
        if fields[0] == addr and fields[1] == iface:
            return fields
    raise AssertionError("no address line for " + addr + " on " + iface)


def tally_named(text, heading):
    for line in report_lines(text)[-4:]:
        words = line.split()
        if words[0] == heading:
            return {words[k]: int(words[k + 1]) for k in range(1, len(words), 2)}
    raise AssertionError("no tally line for " + heading)


def temp_root(source):
    home = tempfile.mkdtemp(prefix="linkroot-")
    root = Path(home) / "host"
    shutil.copytree(source, root)
    return home, root


def halved_root(source):
    home, root = temp_root(source)
    steps = (root / "run" / "link.log").read_text(encoding="ascii").split("\n")[:-1]
    keep = steps[: len(steps) // 2]
    (root / "run" / "link.log").write_text("".join(step + "\n" for step in keep), encoding="ascii")
    return home, root




def test_house_report_matches_the_certified_close():
    """Compares the filed report for the main host with its certified close."""
    assert house_close() == certified_link("expected-house.txt")


def test_second_host_report_matches_the_certified_close():
    """Compares the second host's filed report against the close certified for it."""
    assert second_close() == certified_link("expected-spare.txt")


def test_host_with_no_recorded_steps_matches_its_certified_close():
    """Checks the report filed for a host whose run records no steps."""
    assert still_close() == certified_link("expected-still.txt")


def test_host_whose_run_is_mostly_idle_matches_its_certified_close():
    """Checks the report filed for a host whose run barely stirs anything."""
    assert quiet_close() == certified_link("expected-quiet.txt")


def test_report_length_is_fixed_by_the_declared_estate():
    """Verifies how the report's line count follows from the declared tables."""
    for root, ifaces, bonds, vlans, addrs in (
        (HOUSE_ROOT, 14, 6, 6, 26),
        (SPARE_ROOT, 10, 4, 5, 15),
        (STILL_ROOT, 6, 4, 3, 7),
    ):
        text = closed_link_over(root)
        assert len(report_lines(text)) == 1 + 4 + ifaces + bonds + vlans + addrs + 4
        blocks = link_blocks(text)
        assert len(blocks["iface"]) == ifaces
        assert len(blocks["bond"]) == bonds
        assert len(blocks["vlan"]) == vlans
        assert len(blocks["addr"]) == addrs


def test_halving_the_recorded_run_leaves_the_report_the_same_length():
    """Exercises the shape of the report when the recorded run is cut short."""
    home, root = halved_root(HOUSE_ROOT)
    try:
        short = closed_link_over(root)
        full = house_close()
        assert len(report_lines(short)) == len(report_lines(full))
        moved = sum(1 for a, b in zip(report_lines(full), report_lines(short)) if a != b)
        assert moved > 10
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_no_term_of_the_report_names_the_recorded_run():
    """Checks the report's wording for traces of the recorded run."""
    text = house_close().lower()
    for word in ("step", "log", "history", "moment"):
        assert word not in text
    named = {
        "run", "steps", "claim", "claims", "release", "releases", "detach", "attach",
        "raise", "lower", "link-down", "link-up",
    }
    for piece in text.split():
        assert piece not in named
    for line in report_lines(house_close()):
        assert not line.split()[0].isdigit()


def test_block_headers_are_their_own_column_names_in_their_own_columns():
    """Verifies the header line that opens each block of the report."""
    lines = report_lines(house_close())
    assert lines[1] == IFACE_HEADER
    assert lines[1] == "iface        slot   bond         plc state    rule"
    assert BOND_HEADER == "bond         dec enr cnt flr bearer       state    rule"
    assert VLAN_HEADER == "vlan         parent         tag std state"
    assert ADDR_HEADER == "address            iface        dep state      rule"
    for header in HEADERS:
        assert lines.count(header) == 1


def test_report_ends_with_one_line_feed_and_carries_no_blank_line():
    """Verifies how the report is terminated and whether any line carries slack."""
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        text = closed_link_over(root)
        assert text.endswith("\n")
        assert not text.endswith("\n\n")
        for line in report_lines(text):
            assert line.strip() != ""
            assert line == line.rstrip()


def test_report_carries_no_seal_of_any_kind():
    """Checks the report for seal words and long hexadecimal strings."""
    text = house_close().lower()
    for word in ("sha", "digest", "hash", "checksum", "seal", "crc", "md5"):
        assert word not in text
    for line in report_lines(house_close()):
        for piece in line.split():
            assert not (len(piece) >= 12 and all(c in "0123456789abcdef" for c in piece))


def test_head_line_counts_come_from_the_declared_tables():
    """Verifies the head line the report opens with."""
    words = report_lines(house_close())[0].split()
    assert words[0] == "host"
    assert words[1] == "netherhall"
    assert words[2:] == [
        "interfaces", "14", "bonds", "6", "vlans", "6", "addresses", "26", "carrying", "2",
    ]


def test_carrying_counts_the_bonds_whose_carry_is_held():
    """Weighs the carrying figure on the head line against the bond block."""
    for root, expected in ((HOUSE_ROOT, 2), (SPARE_ROOT, 2), (STILL_ROOT, 1), (QUIET_ROOT, 2)):
        text = closed_link_over(root)
        words = report_lines(text)[0].split()
        held = sum(1 for line in link_blocks(text)["bond"]
                   if link_fields(line, BOND_WIDTHS, BOND_ALIGN)[5] != "-")
        assert int(words[-1]) == expected
        assert int(words[-1]) == held


def test_every_block_follows_the_order_of_its_own_table():
    """Checks the order in which each block lists its entries."""
    plan = (
        ("interfaces.table", "iface", IFACE_WIDTHS, IFACE_ALIGN),
        ("bonds.table", "bond", BOND_WIDTHS, BOND_ALIGN),
        ("vlans.table", "vlan", VLAN_WIDTHS, VLAN_ALIGN),
    )
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT):
        text = closed_link_over(root)
        for table, block, widths, aligns in plan:
            declared = [raw.split(":")[0].strip()
                        for raw in Path(root, "links", table).read_text(
                            encoding="ascii").split("\n") if raw.strip()]
            printed = [link_fields(line, widths, aligns)[0] for line in link_blocks(text)[block]]
            assert printed == declared


def test_every_interface_takes_one_state_and_one_token_from_its_closed_sets():
    """Verifies that interface lines pair recognised state and rule words."""
    owner = {
        "bear.carry": "BEARING", "bear.own": "BEARING",
        "spare.ladder": "SPARE", "spare.vacant": "SPARE",
        "bare.detached": "BARE", "bare.idle": "BARE",
        "dark.link-down": "DARK", "cold.never-up": "UNWIRED",
    }
    assert set(owner) == IFACE_TOKENS
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        for line in link_blocks(closed_link_over(root))["iface"]:
            fields = link_fields(line, IFACE_WIDTHS, IFACE_ALIGN)
            assert fields[4] in IFACE_STATES
            assert fields[5] in IFACE_TOKENS
            assert owner[fields[5]] == fields[4]


def test_a_link_that_never_stood_reads_unwired_until_a_link_up_reaches_it():
    """Verifies how an interface whose link has not yet stood is ruled."""
    assert iface_line(house_close(), "eth12")[4:] == ("UNWIRED", "cold.never-up")
    assert iface_line(second_close(), "enp7")[4:] == ("UNWIRED", "cold.never-up")
    assert iface_line(still_close(), "nic5")[4:] == ("UNWIRED", "cold.never-up")
    assert iface_line(quiet_close(), "nic5")[4:] == ("BEARING", "bear.carry")


def test_a_member_whose_link_moved_keeps_its_unchanged_place_on_the_ladder():
    """Checks the ladder place shown for a member whose link changed."""
    assert iface_line(house_close(), "eth7") == (
        "eth7", "p07", "bond1", "4", "DARK", "dark.link-down")
    assert iface_line(second_close(), "enp4") == (
        "enp4", "s4", "team1", "2", "DARK", "dark.link-down")
    assert iface_line(house_close(), "eth5")[2:4] == ("bond1", "3")
    assert iface_line(second_close(), "enp3")[2:4] == ("team1", "1")


def test_interface_in_no_bond_holding_a_standing_address_bears_on_its_own():
    """Verifies how an interface outside any bond that holds a standing address is ruled."""
    assert iface_line(house_close(), "eth10") == ("eth10", "p10", "-", "-", "BEARING", "bear.own")


def test_member_holding_a_standing_address_is_still_ruled_on_the_bond_rungs():
    """Verifies how a bond member holding a standing address is ruled."""
    assert addr_line(still_close(), "192.168.7.9", "nic0")[3:] == ("STANDING", "stand.sole")
    assert iface_line(still_close(), "nic0") == ("nic0", "b00", "agg3", "1", "SPARE", "spare.ladder")


def test_bare_tells_apart_an_interface_that_left_a_bond_from_one_that_never_held_a_place():
    """Checks how interfaces standing outside any bond are told apart."""
    assert iface_line(house_close(), "eth8") == ("eth8", "p08", "-", "-", "BARE", "bare.detached")
    assert iface_line(second_close(), "enp6")[4:] == ("BARE", "bare.detached")
    assert iface_line(second_close(), "enp9") == ("enp9", "s9", "-", "-", "BARE", "bare.idle")


def test_every_bond_takes_one_state_and_one_token_from_its_closed_sets():
    """Confirms the bond block draws its state and rule words from known sets."""
    owner = {
        "full.assembled": "FULL", "thin.short": "THIN",
        "stint.floor-lost": "STINTED", "stint.held-over": "STINTED",
        "down.lowered": "DOWN", "down.no-member": "DOWN",
        "cold.never-raised": "UNMADE",
    }
    assert set(owner) == BOND_TOKENS
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        for line in link_blocks(closed_link_over(root))["bond"]:
            fields = link_fields(line, BOND_WIDTHS, BOND_ALIGN)
            assert fields[6] in BOND_STATES
            assert fields[7] in BOND_TOKENS
            assert owner[fields[7]] == fields[6]


def test_bond_bears_on_its_bottom_most_counting_member():
    """Verifies which member of a bond the bearer column names."""
    assert bond_line(house_close(), "bond1")[5] == "eth5"
    assert iface_line(house_close(), "eth5")[3] == "3"
    assert iface_line(house_close(), "eth1")[3:] == ("1", "SPARE", "spare.ladder")
    assert bond_line(second_close(), "team2")[5] == "enp0"
    assert iface_line(second_close(), "enp0")[3] == "2"


def test_the_carry_does_not_fail_back_to_a_member_that_returns_below_it():
    """Exercises the bearer column after a member comes back onto the ladder."""
    assert bond_line(house_close(), "bond1")[5] == "eth5"
    assert iface_line(house_close(), "eth3")[3:] == ("2", "SPARE", "spare.ladder")
    assert bond_line(quiet_close(), "agg3")[5] == "nic4"
    assert iface_line(quiet_close(), "nic3")[3] == "1"


def test_counted_column_counts_only_members_whose_link_stands():
    """Verifies what the counted column of a bond line reckons."""
    assert bond_line(house_close(), "bond1")[1:5] == ("4", "4", "3", "3")
    assert bond_line(second_close(), "team1")[1:5] == ("3", "3", "2", "0")
    assert bond_line(still_close(), "agg0")[1:5] == ("2", "2", "0", "1")


def test_the_lower_bond_in_the_table_takes_a_doubly_declared_member():
    """Verifies how a member that two bonds declare is settled between them."""
    assert iface_line(house_close(), "eth4")[2:4] == ("bond2", "2")
    assert bond_line(house_close(), "bond0")[1:3] == ("3", "2")
    assert iface_line(second_close(), "enp0")[2] == "team2"
    assert bond_line(second_close(), "team0")[1:3] == ("3", "2")


def test_an_attached_member_joins_the_top_of_the_ladder():
    """Verifies the ladder place a member attached during the run receives."""
    assert iface_line(quiet_close(), "nic3")[2:4] == ("agg3", "1")
    assert iface_line(quiet_close(), "nic0")[2:4] == ("agg3", "2")
    assert iface_line(still_close(), "nic3")[2:4] == ("agg3", "2")


def test_an_attach_takes_nothing_where_the_bond_is_down_or_the_rule_refuses():
    """Exercises enrolment when an attach reaches a bond standing lowered."""
    assert bond_line(quiet_close(), "agg1")[2] == "2"
    assert iface_line(quiet_close(), "nic0")[2] == "agg3"
    assert bond_line(quiet_close(), "agg2")[1:5] == ("0", "0", "0", "0")
    assert bond_line(quiet_close(), "agg3")[1:5] == ("3", "3", "3", "2")


def test_an_attach_by_a_lower_bond_takes_the_member_from_its_holder():
    """Checks enrolment when one bond attaches a member another already holds."""
    assert iface_line(quiet_close(), "nic1")[2:4] == ("agg1", "1")
    assert bond_line(quiet_close(), "agg0")[1:3] == ("2", "1")
    assert bond_line(quiet_close(), "agg1")[1:3] == ("1", "2")


def test_a_raise_rebuilds_the_ladder_from_the_member_table():
    """Exercises the ladder of a bond raised again during the run."""
    assert bond_line(house_close(), "bond0")[1:5] == ("3", "2", "2", "2")
    assert iface_line(house_close(), "eth0")[3] == "1"
    assert iface_line(house_close(), "eth2")[3] == "2"
    assert iface_line(house_close(), "eth9")[2] == "bond3"


def test_a_lowered_bond_keeps_its_ladder_and_reads_down_lowered():
    """Verifies how a bond lowered during the run and its members are ruled."""
    assert bond_line(house_close(), "bond5") == (
        "bond5", "1", "1", "1", "1", "-", "DOWN", "down.lowered")
    assert iface_line(house_close(), "eth13")[2:] == ("bond5", "1", "SPARE", "spare.vacant")


def test_a_bond_never_raised_reads_unmade_with_an_empty_ladder():
    """Verifies how a bond that was never raised is reported."""
    assert bond_line(house_close(), "bond4") == (
        "bond4", "1", "0", "0", "1", "-", "UNMADE", "cold.never-raised")


def test_a_bond_standing_with_no_member_reads_down_no_member():
    """Verifies how a bond standing with nothing enrolled is ruled."""
    assert bond_line(second_close(), "team3") == (
        "team3", "1", "0", "0", "1", "-", "DOWN", "down.no-member")
    assert bond_line(still_close(), "agg2") == (
        "agg2", "0", "0", "0", "0", "-", "DOWN", "down.no-member")


def test_a_bond_under_its_floor_stays_up_and_reads_stinted():
    """Verifies how a bond whose counted members fall below its floor is ruled."""
    assert bond_line(house_close(), "bond2") == (
        "bond2", "3", "2", "1", "2", "-", "STINTED", "stint.floor-lost")
    assert bond_line(second_close(), "team0")[6:] == ("STINTED", "stint.floor-lost")


def test_reduced_standing_survives_its_members_coming_back():
    """Checks how a bond that dipped and recovered its members is ruled."""
    assert bond_line(house_close(), "bond0") == (
        "bond0", "3", "2", "2", "2", "-", "STINTED", "stint.held-over")


def test_a_bond_whose_members_have_all_lost_their_links_is_not_down():
    """Verifies how a bond is ruled once none of its members counts."""
    assert bond_line(still_close(), "agg0")[6:] == ("STINTED", "stint.floor-lost")
    assert bond_line(still_close(), "agg1") == (
        "agg1", "1", "1", "0", "0", "-", "THIN", "thin.short")


def test_a_bond_of_floor_zero_never_reaches_stinted():
    """Verifies how a bond declaring no member floor is ruled."""
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        for line in link_blocks(closed_link_over(root))["bond"]:
            fields = link_fields(line, BOND_WIDTHS, BOND_ALIGN)
            if fields[4] == "0":
                assert fields[6] != "STINTED"
    assert bond_line(second_close(), "team1")[4:] == ("0", "enp8", "THIN", "thin.short")


def test_every_member_of_a_bond_with_a_vacant_carry_reads_spare_vacant():
    """Verifies how the members of a bond with no bearer named are ruled."""
    for name in ("eth0", "eth2"):
        assert iface_line(house_close(), name)[4:] == ("SPARE", "spare.vacant")
    assert bond_line(house_close(), "bond0")[5] == "-"
    assert iface_line(house_close(), "eth4")[4:] == ("SPARE", "spare.vacant")


def test_thin_is_short_of_the_declared_count_and_full_reaches_it():
    """Checks how a bond line distinguishes complete membership from a shortfall."""
    fields = bond_line(second_close(), "team1")
    assert int(fields[3]) < int(fields[1])
    assert fields[5] == "enp8"
    assert fields[6] == "THIN"
    assert bond_line(house_close(), "bond3") == (
        "bond3", "2", "2", "2", "2", "eth11", "FULL", "full.assembled")
    assert bond_line(quiet_close(), "agg1")[1:4] == ("1", "2", "1")
    assert bond_line(quiet_close(), "agg1")[6] == "FULL"


def test_every_vlan_takes_one_state_from_the_closed_four():
    """Confirms the state words that appear on VLAN interface lines."""
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        for line in link_blocks(closed_link_over(root))["vlan"]:
            assert link_fields(line, VLAN_WIDTHS, VLAN_ALIGN)[4] in VLAN_STATES


def test_the_vlan_block_carries_no_rule_token_column():
    """Verifies which columns a VLAN interface line ends up carrying."""
    for line in link_blocks(house_close())["vlan"]:
        fields = link_fields(line, VLAN_WIDTHS, VLAN_ALIGN)
        assert len(fields) == 5
        assert line.rstrip().endswith(fields[4])
        for token in IFACE_TOKENS | BOND_TOKENS | ADDR_TOKENS:
            assert token not in line


def test_a_vlan_is_ruled_without_any_reference_to_its_parent():
    """Verifies how a VLAN interface is ruled when its parent has faltered."""
    assert vlan_line(house_close(), "vl33") == ("vl33", "eth12", "33", "1", "UP")
    assert vlan_line(second_close(), "vif8") == ("vif8", "enp7", "8", "1", "UP")
    assert vlan_line(house_close(), "vl44") == ("vl44", "bond2", "44", "1", "UP")
    assert bond_line(house_close(), "bond2")[6] == "STINTED"
    assert vlan_line(still_close(), "tag0")[4] == "QUIET"


def test_a_lowered_or_unmade_vlan_still_shows_the_record_standing_on_it():
    """Checks what a VLAN interface lowered or never raised still reports."""
    assert vlan_line(house_close(), "vl22") == ("vl22", "bond1", "22", "1", "DOWN")
    assert addr_line(house_close(), "10.20.0.5", "vl22")[3] == "STANDING"
    assert vlan_line(second_close(), "vif7") == ("vif7", "team0", "7", "1", "DOWN")
    assert vlan_line(second_close(), "vifa") == ("vifa", "team3", "10", "0", "UNMADE")
    assert vlan_line(still_close(), "tag2") == ("tag2", "agg3", "300", "1", "UNMADE")


def test_the_standing_record_column_counts_standing_and_not_claimed():
    """Weighs the standing column of a VLAN line against the address block."""
    assert vlan_line(house_close(), "vl66") == ("vl66", "bond2", "66", "0", "QUIET")
    assert vlan_line(second_close(), "vif9")[3] == "2"
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        text = closed_link_over(root)
        for line in link_blocks(text)["vlan"]:
            fields = link_fields(line, VLAN_WIDTHS, VLAN_ALIGN)
            held = sum(1 for row in link_blocks(text)["addr"]
                       if link_fields(row, ADDR_WIDTHS, ADDR_ALIGN)[1] == fields[0]
                       and link_fields(row, ADDR_WIDTHS, ADDR_ALIGN)[3] == "STANDING")
            assert int(fields[3]) == held


def test_address_block_ascends_by_address_text_then_by_interface():
    """Verifies the order the address block lists its records in."""
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT):
        keys = [link_fields(line, ADDR_WIDTHS, ADDR_ALIGN)[:2]
                for line in link_blocks(closed_link_over(root))["addr"]]
        assert keys == sorted(keys)
    printed = [link_fields(line, ADDR_WIDTHS, ADDR_ALIGN)[0]
               for line in link_blocks(house_close())["addr"]]
    assert printed.index("10.20.0.13") < printed.index("10.20.0.5")


def test_every_address_record_takes_one_state_and_one_token_from_its_closed_sets():
    """Examines which state and rule words appear together on address lines."""
    owner = {
        "stand.sole": "STANDING", "stand.won": "STANDING",
        "oust.stinted": "OUSTED", "oust.depth": "OUSTED", "oust.place": "OUSTED",
        "aside.stinted": "SET-ASIDE", "drop.released": "DROPPED",
        "cold.never-claimed": "UNCLAIMED",
    }
    assert set(owner) == ADDR_TOKENS
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        for line in link_blocks(closed_link_over(root))["addr"]:
            fields = link_fields(line, ADDR_WIDTHS, ADDR_ALIGN)
            assert fields[3] in ADDR_STATES
            assert fields[4] in ADDR_TOKENS
            assert owner[fields[4]] == fields[3]


def test_stack_depth_counts_the_interface_the_record_names():
    """Verifies what the depth column of an address line reckons."""
    assert addr_line(house_close(), "10.20.0.1", "eth0")[2] == "1"
    assert addr_line(house_close(), "10.20.0.1", "bond1")[2] == "2"
    assert addr_line(house_close(), "10.20.0.1", "vl11")[2] == "3"
    assert addr_line(house_close(), "10.20.0.13", "vl33")[2] == "2"
    assert addr_line(still_close(), "192.168.7.1", "tag1")[2] == "2"
    assert addr_line(still_close(), "192.168.7.13", "tag0")[2] == "3"


def test_the_deeper_record_takes_a_contested_address():
    """Verifies how an address claimed at differing depths is settled."""
    assert addr_line(house_close(), "10.20.0.1", "vl11")[3:] == ("STANDING", "stand.won")
    assert addr_line(house_close(), "10.20.0.1", "bond1")[3:] == ("OUSTED", "oust.depth")
    assert addr_line(house_close(), "10.20.0.1", "eth0")[3:] == ("OUSTED", "oust.depth")


def test_the_last_declared_record_takes_an_address_tied_on_depth():
    """Checks how an address contested at equal depth is settled."""
    assert addr_line(house_close(), "10.20.0.41", "eth10")[3:] == ("STANDING", "stand.won")
    assert addr_line(house_close(), "10.20.0.41", "eth13")[3:] == ("OUSTED", "oust.place")
    assert addr_line(house_close(), "10.20.0.41", "eth9")[3:] == ("OUSTED", "oust.place")
    assert addr_line(second_close(), "172.16.4.10", "vif8")[3:] == ("STANDING", "stand.won")
    assert addr_line(second_close(), "172.16.4.10", "team2")[3:] == ("OUSTED", "oust.place")


def test_the_moment_of_claim_never_decides_a_contested_address():
    """Checks whether the order of claiming bears on a contested address."""
    assert addr_line(house_close(), "10.20.0.29", "vl55")[3:] == ("STANDING", "stand.won")
    assert addr_line(house_close(), "10.20.0.29", "eth11")[3:] == ("OUSTED", "oust.depth")
    assert addr_line(house_close(), "10.20.0.29", "bond3")[3:] == ("OUSTED", "oust.depth")


def test_a_record_on_a_bond_in_reduced_standing_is_weighed_last():
    """Verifies how an address declared on a bond in reduced standing fares."""
    assert addr_line(house_close(), "10.20.0.5", "bond0")[3:] == ("OUSTED", "oust.stinted")
    assert addr_line(house_close(), "10.20.0.9", "bond2")[3:] == ("OUSTED", "oust.stinted")
    assert addr_line(second_close(), "172.16.4.6", "team0")[3:] == ("OUSTED", "oust.stinted")
    assert addr_line(still_close(), "192.168.7.1", "agg0")[3:] == ("OUSTED", "oust.stinted")


def test_records_beyond_the_top_ranked_one_are_set_aside():
    """Checks how the later addresses of a bond in reduced standing are ruled."""
    assert addr_line(house_close(), "10.20.0.21", "bond0")[3:] == ("SET-ASIDE", "aside.stinted")
    assert addr_line(house_close(), "10.20.0.25", "bond2")[3:] == ("SET-ASIDE", "aside.stinted")
    assert addr_line(second_close(), "172.16.4.14", "team0")[3:] == ("SET-ASIDE", "aside.stinted")
    assert addr_line(still_close(), "192.168.7.5", "agg0")[3:] == ("SET-ASIDE", "aside.stinted")


def test_a_set_aside_record_stands_nowhere_and_only_a_bond_ever_carries_one():
    """Examines which interfaces carry the records held back and how those stand."""
    assert vlan_line(house_close(), "vl11")[3] == "1"
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        text = closed_link_over(root)
        bonds = {link_fields(line, BOND_WIDTHS, BOND_ALIGN)[0]
                 for line in link_blocks(text)["bond"]}
        for line in link_blocks(text)["addr"]:
            fields = link_fields(line, ADDR_WIDTHS, ADDR_ALIGN)
            if fields[3] == "SET-ASIDE":
                assert fields[1] in bonds
                assert bond_line(text, fields[1])[6] == "STINTED"


def test_a_released_record_is_dropped_only_where_it_was_not_claimed_again():
    """Verifies how an address released during the run, and one reclaimed after, are ruled."""
    assert addr_line(house_close(), "10.20.0.37", "bond1")[3:] == ("DROPPED", "drop.released")
    assert addr_line(second_close(), "172.16.4.18", "enp7")[3:] == ("DROPPED", "drop.released")
    assert addr_line(quiet_close(), "192.168.7.9", "nic0")[3:] == ("STANDING", "stand.sole")
    assert tally_named(quiet_close(), "addresses")["DROPPED"] == 0


def test_a_record_never_claimed_reads_unclaimed_and_a_sole_one_stands_alone():
    """Verifies how an address no record ever claimed, and one claimed alone, are ruled."""
    assert addr_line(house_close(), "10.20.0.33", "eth1")[3:] == ("UNCLAIMED", "cold.never-claimed")
    assert addr_line(second_close(), "172.16.4.22", "vifa")[3:] == (
        "UNCLAIMED", "cold.never-claimed")
    assert addr_line(house_close(), "10.20.0.45", "eth7")[3:] == ("STANDING", "stand.sole")
    assert addr_line(still_close(), "192.168.7.17", "tag2")[3:] == ("STANDING", "stand.sole")


def test_a_record_is_weighed_without_reference_to_what_it_stands_on():
    """Checks whether the state of the interface beneath an address bears on it."""
    assert addr_line(house_close(), "10.20.0.45", "eth7")[3] == "STANDING"
    assert iface_line(house_close(), "eth7")[4] == "DARK"
    assert addr_line(still_close(), "192.168.7.1", "nic1")[3] == "OUSTED"
    assert iface_line(still_close(), "nic1")[4] == "UNWIRED"
    assert addr_line(house_close(), "10.20.0.29", "bond3")[3] == "OUSTED"
    assert addr_line(second_close(), "172.16.4.2", "team1")[3:] == ("OUSTED", "oust.depth")
    assert addr_line(second_close(), "172.16.4.2", "vif7")[3:] == ("STANDING", "stand.won")


def test_exactly_one_record_stands_for_every_contested_address():
    """Verifies how many records of a single address can stand at the close."""
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        held = {}
        for line in link_blocks(closed_link_over(root))["addr"]:
            fields = link_fields(line, ADDR_WIDTHS, ADDR_ALIGN)
            held.setdefault(fields[0], []).append(fields[3])
        for states in held.values():
            assert states.count("STANDING") <= 1
            if "OUSTED" in states:
                assert states.count("STANDING") == 1


def test_the_four_tallies_close_the_report_in_their_fixed_order():
    """Verifies the tally lines that close the report and the words they list."""
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        last = report_lines(closed_link_over(root))[-4:]
        assert last[0].split()[0] == "interfaces"
        assert last[1].split()[0] == "bonds"
        assert last[2].split()[0] == "vlans"
        assert last[3].split()[0] == "addresses"
        assert last[0].split()[1::2] == list(IFACE_STATES)
        assert last[1].split()[1::2] == list(BOND_STATES)
        assert last[2].split()[1::2] == list(VLAN_STATES)
        assert last[3].split()[1::2] == list(ADDR_STATES)


def test_every_state_prints_in_its_tally_even_at_zero():
    """Checks whether a state with no lines still shows in its tally."""
    text = still_close()
    assert tally_named(text, "interfaces")["BARE"] == 0
    assert tally_named(text, "interfaces")["DARK"] == 0
    assert tally_named(text, "bonds")["UNMADE"] == 0
    assert tally_named(text, "vlans")["DOWN"] == 0
    assert tally_named(text, "addresses")["DROPPED"] == 0


def test_each_tally_agrees_with_the_lines_of_the_block_above_it():
    """Verifies each tally against the block of lines it sums up."""
    for root in (HOUSE_ROOT, SPARE_ROOT, STILL_ROOT, QUIET_ROOT):
        text = closed_link_over(root)
        blocks = link_blocks(text)
        plan = (
            ("iface", IFACE_WIDTHS, IFACE_ALIGN, 4, "interfaces", IFACE_STATES),
            ("bond", BOND_WIDTHS, BOND_ALIGN, 6, "bonds", BOND_STATES),
            ("vlan", VLAN_WIDTHS, VLAN_ALIGN, 4, "vlans", VLAN_STATES),
            ("addr", ADDR_WIDTHS, ADDR_ALIGN, 3, "addresses", ADDR_STATES),
        )
        for block, widths, aligns, at, heading, states in plan:
            seen = {}
            for line in blocks[block]:
                state = link_fields(line, widths, aligns)[at]
                seen[state] = seen.get(state, 0) + 1
            assert tally_named(text, heading) == {s: seen.get(s, 0) for s in states}


def test_a_run_of_idle_steps_moves_nothing_the_estate_did_not_move():
    """Examines which report lines differ between two closely matched hosts."""
    still = report_lines(still_close())
    quiet = report_lines(quiet_close())
    assert len(still) == len(quiet)
    moved = {k for k, (a, b) in enumerate(zip(still, quiet)) if a != b}
    assert moved == {0, 2, 3, 4, 5, 7, 9, 10, 25, 26}


def test_selfcheck_files_the_same_report_and_says_nothing():
    """Exercises the self-check flag and what it leaves on the streams and on disk."""
    for root, name in ((HOUSE_ROOT, "expected-house.txt"), (SPARE_ROOT, "expected-spare.txt")):
        done, target, home = link_close(root, ("--selfcheck",))
        try:
            assert done.returncode == 0
            assert done.stdout == ""
            assert done.stderr == ""
            assert target.read_text(encoding="ascii") == certified_link(name)
        finally:
            shutil.rmtree(home, ignore_errors=True)


def test_a_clean_run_says_nothing_and_repeats_itself_byte_for_byte():
    """Exercises a clean run's output streams and a second run over the same input."""
    first, target, home = link_close(HOUSE_ROOT)
    try:
        assert first.returncode == 0
        assert first.stdout == ""
        assert first.stderr == ""
        once = target.read_text(encoding="ascii")
        again = run_linkctl(HOUSE_ROOT, target)
        assert again.returncode == 0
        assert again.stdout == ""
        assert target.read_text(encoding="ascii") == once
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_the_report_directory_is_cleared_before_the_report_is_filed():
    """Checks what becomes of files already sitting where the report is filed."""
    home = tempfile.mkdtemp(prefix="linkctl-")
    try:
        filed = Path(home) / "filed"
        (filed / "older").mkdir(parents=True)
        (filed / "older" / "leftover.txt").write_text("stale\n", encoding="ascii")
        (filed / "stray.txt").write_text("stale\n", encoding="ascii")
        done = run_linkctl(HOUSE_ROOT, filed / "link-state-report.txt")
        assert done.returncode == 0
        assert sorted(p.name for p in filed.iterdir()) == ["link-state-report.txt"]
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_the_link_root_is_left_exactly_as_it_was_found():
    """Verifies the state of the read-only input tree after a run."""
    home, root = temp_root(HOUSE_ROOT)
    try:
        before = {str(p.relative_to(root)): p.read_bytes()
                  for p in sorted(root.rglob("*")) if p.is_file()}
        done, _target, out = link_close(root)
        shutil.rmtree(out, ignore_errors=True)
        assert done.returncode == 0
        after = {str(p.relative_to(root)): p.read_bytes()
                 for p in sorted(root.rglob("*")) if p.is_file()}
        assert after == before
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_the_tool_files_the_house_close_from_its_own_sources_by_default():
    """Verifies the report the tool files from its own sources at the default place."""
    sources = sorted(p.name for p in Path(LINKCTL_SRC).glob("*.go"))
    assert sources
    assert Path(LINKCTL).exists()
    assert Path(LINKCTL_SRC, "go.mod").exists()
    if not Path("/app/var/lib/linkctl").exists():
        pytest.skip("no default report directory on this host")
    where = dict(os.environ)
    where.pop("LINK_ROOT", None)
    where.pop("LINK_STATE_REPORT", None)
    done = subprocess.run([LINKCTL], capture_output=True, text=True, env=where, check=False)
    assert done.returncode == 0
    filed = Path("/app/var/lib/linkctl/link-state-report.txt")
    assert filed.read_text(encoding="ascii") == certified_link("expected-house.txt")

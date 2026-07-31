Report the closing state of this host's network interfaces after its recorded link run. Every
physical interface, bond, VLAN interface and declared address appears with the state it ended in and,
apart from the VLANs, the rule that decided it.

A physical interface ends in one of five states:
- BEARING: its link stands and it carries, for its bond or on its own standing address.
- SPARE: its link stands and a bond's ladder holds it, but it does not carry.
- BARE: its link stands, no bond names it, and no address on it stands.
- DARK: its link stood once and does not stand at the close.
- UNWIRED: its link never stood.

A bond ends in one of five states:
- FULL: every member it declares is enrolled and counted.
- THIN: short of full membership, counted members at or above its member floor.
- STINTED: counted members under the floor, or under it earlier and not cleared since. It stays up
  in a reduced standing.
- DOWN: lowered and not raised again, or standing with no member enrolled.
- UNMADE: never raised.

A VLAN interface ends UP, standing with an address on it standing; QUIET, standing with none; DOWN,
lowered and not raised; or UNMADE, never raised. An address closes STANDING; OUSTED, another
interface's claim to it holding it; SET-ASIDE, its bond stinted and this not that bond's first
claimed address; DROPPED, released and not claimed again; or UNCLAIMED.

The link rules are at /app/etc/linkctl/rules, numbered N001 through N160 without a gap under an
index, and those clauses are the whole law. Several settle bonding, VLAN stacking and duplicate
addresses differently from ordinary practice and say so where they stand; no habit decides a state.

The input is read-only under LINK_ROOT, default /app/host: the interfaces, their slots and their
standing at the open; the bonds, their member floors and whether each stood raised; the
members each bond declares, in ladder order; the VLANs with their parent and tag; the address table
in rank order, each line naming an address, the interface declaring it and its claim at
the open; and the run, one numbered step per line in eight kinds: links down and up, members
detached and attached, bonds and VLANs raised and lowered, addresses claimed and released.

For reference, these twenty three tokens name the rule behind each state and no others. BEARING:
bear.carry, bear.own, by whether it carries for a bond or alone. SPARE: spare.ladder,
spare.vacant, by whether another member carries or the carry stands vacant. BARE:
bare.detached, bare.idle, by whether it ever held a place. DARK: dark.link-down. UNWIRED:
cold.never-up. FULL: full.assembled. THIN: thin.short. STINTED: stint.floor-lost and
stint.held-over, by whether counted members are under the floor now or back at it. DOWN:
down.lowered, down.no-member. UNMADE: cold.never-raised. STANDING: stand.sole, stand.won, by whether
any other record was weighed against it. OUSTED: oust.stinted, oust.depth, oust.place, by which test
it lost on. SET-ASIDE: aside.stinted. DROPPED: drop.released. UNCLAIMED: cold.never-claimed.

Distinctions the rules draw. SPARE and BARE both stand carrying nothing; only the SPARE one is
enrolled in a bond and counts toward its floor. A bond holding members none of which counts is
STINTED, not DOWN: the no-member test asks about enrolment and is weighed first.

The report goes to the full path named by LINK_STATE_REPORT, default
/app/var/lib/linkctl/link-state-report.txt: a head line, one line per interface, bond, VLAN and
address, then four tallies, in the layout clauses N144 through N158 fix, byte for byte. It carries no
seal, answers a --selfcheck flag as clause N143 fixes, showing repeatability only and not that a
state is right, prints nothing on a clean run, leaves LINK_ROOT untouched, and is identical over
unchanged input.

The tool's own sources stand at /app/opt/linkctl, and the report that counts is the one it files
after being rebuilt from them and run over the input, which as delivered does not yet rule every
interface and every address as the rules require, so bring it into accord before the report is filed.

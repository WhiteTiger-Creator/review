# Prepaid gondola-schedule threshold report: contract

`report.py` replays a timestamped stream of data-usage and credit events
against per-gondola and per-line data allocations and prints a deterministic
ledger of usage verdicts, surge-state transitions, and standby-pool activity.

```
python3 report.py <line-config> <boarding-stream>
```

The two positional arguments are paths to text files. The ledger is written to
standard output, one record per line, terminated by a newline.

## Allowance model

Every allocation (whether it belongs to a gondola or to a line) has three
integer parameters: a **threshold** (`soft`), a **limit** (`hard`,
`hard >= soft >= 0`), and a **surge** window measured in ticks (`grace >= 0`).
Usage is a count of MB, a non-negative integer that starts at `0`. A line
may carry one extra integer parameter beyond these three, its **standby pool**
capacity (`pool >= 0`, defaulting to `0` when the field is omitted); see the
standby-pool section below.

Each gondola belongs to exactly one line. Both the gondola's own allocation
and its line's allocation are evaluated for every boarding event; a boarding event is
permitted only when **both** allocations permit it (most-restrictive wins).

An allocation is in one of three usage regimes at any tick:

- **under threshold**: current usage `<= soft`.
- **over threshold, within surge**: usage `> soft` and the surge window has not
  yet expired. Usage events are still permitted (subject to the limit).
- **over threshold, surge expired**: usage `> soft` and the surge window has
  expired. The threshold now behaves like a limit.

The **limit is absolute**: a boarding event that would drive usage strictly above
`hard` is rejected immediately, regardless of surge state.

## Boost-timer lifecycle

Each allocation carries an independent surge timer. The gondola timer and the
line timer never share state.

- The timer is **started** at tick `T` the first time a boarding event drives an
  allocation's usage strictly above its threshold while the timer is not
  already running. The surge window then covers ticks `T` through `T + grace`
  inclusive.
- While usage stays above the threshold, the timer keeps running across
  later ticks.
- **Expiry is inclusive at the far edge:** at any tick `now`, the window is
  still open when `now <= T + grace` and has expired when `now > T + grace`.
  So a boarding event at exactly `T + grace` is still within surge, and one at
  `T + grace + 1` is past it.
- If usage drops back to `<= soft` (because a credit lowered it), the timer is
  **cancelled**: it stops running and no expiry is recorded.
- A later re-crossing above the threshold **restarts a full new surge
  window** from the tick of the re-crossing. It does not resume a previous
  partially-elapsed window; the remaining time from any earlier window is
  discarded.

## Events

The usage stream is processed in the order the lines appear. Each event line is

```
<tick> BOARD <gondola> <MB>
```

or

```
<tick> ALIGHT <gondola> <MB>
```

where `<tick>` is a non-negative integer, `<gondola>` names a configured
gondola, and `<MB>` is a positive integer.

A `BOARD` requests `<MB>` additional MB for `<gondola>`. The request also
counts against the gondola's line, because every MB the gondola holds is
also held by its line. The boarding event is **all-or-nothing**: the full request
must be satisfiable, or the boarding event is denied and no counter, debt, or
standby pool changes.

## Deciding a BOARD

For a `BOARD` of `n` MB by a gondola (and its line) at the event tick, the
engine determines how the request can be satisfied.

A **limit violation is absolute and checked first**: if adding `n` to the
gondola's own usage would exceed the gondola limit the boarding event is denied
with `GOND_LIMIT`; otherwise if adding `n` to the line's usage would exceed the
line limit it is denied with `LINE_LIMIT`. The gondola check precedes the line
check.

Otherwise the engine works out how much of the request can be granted
**normally**, that is charged directly against the gondola and line usage
counters. The normal ceiling for an allocation is its limit while the allocation is
under the threshold or within an open surge window, and its threshold
threshold once the allocation is over the threshold with its surge
expired. The amount that can be granted normally is `n` capped by how far each
of the two allocations is below its own normal ceiling, taking the smaller of the
two. A normal grant that drives an allocation strictly above its threshold
threshold starts that allocation's surge window exactly as described above.

## Shared line standby pool

When the normal grant cannot cover the full request, because the binding
threshold-or-surge ceiling is reached, the leftover shortfall is **borrowed**
from the line's shared standby pool rather than denied, provided the pool has at
least that many MB free. Borrowed MB are an accommodation drawn from a separate
pool: they satisfy the boarding event but are **not** added to the gondola or
line usage counters, so they never push usage above any limit and they do **not**
start a surge timer. The borrowed amount is recorded as that gondola's
outstanding **debt** against the standby pool and the pool's free capacity drops
by the same amount. Because the boarding event is all-or-nothing, a shortfall the
free pool cannot fully cover means the whole boarding event is denied with
`STANDBY_EMPTY` and nothing changes.

A `ALIGHT` releasing `<MB>` MB for a gondola is processed in a fixed order:
the credited MB **first return that gondola's own outstanding pool debt**,
returning MB to the shared standby pool, and only the remainder left after the
debt is settled reduces the gondola's own usage (and its line's). Repayment
unwinds the gondola's borrows **newest first**, so the most recently borrowed
amount is repaid before older ones, until either the credited MB are exhausted
or the gondola's debt reaches zero. Because every event names a single
gondola and is applied in stream order, the repayment of a contended pool and
any later boarding event that the freed-up pool enables are fully determined by
that order. A credit never drives a usage counter below `0`; once any debt is
settled, crediting more than the gondola's own usage clamps that usage at
`0`. A credit that leaves usage back at or under the threshold cancels
a running surge timer for that allocation.

## Output records and ordering

For each event the engine processes, it emits records in this canonical order.

A `ALIGHT` emits a single `<tick> RETURN <gondola> <n>` line when, and only
when, it repays `n > 0` MB of pool debt (`n` is the total repaid by that
credit); beyond that a `ALIGHT` produces no output.

A `BOARD` emits its **verdict line** first, either `<tick> BOARDED`, or
`<tick> REJECT <REASON>` where the reason is one of `GOND_LIMIT`, `LINE_LIMIT`, or
`STANDBY_EMPTY`. When allowed, the verdict line is followed by any surge-state
transition lines this boarding event caused, the **gondola transition before
the line transition**, each being `<tick> SURGE_START <GOND|LINE> <name>` when a
window opens (or reopens) at this tick. If the boarding event drew on the standby
pool, a final `<tick> STANDBY <gondola> <n>` line follows the transition
lines, where `n` is the borrowed amount. A `SURGE_START` is emitted only on a
transition from not-running to running (including a restart after a cancel);
staying over the threshold across ticks does not re-emit it, and
borrowing from the standby pool never emits one.

## Errors

If either input file cannot be read or parsed, references an unknown gondola,
or violates the structural rules above (`hard < soft`, negative parameters, a
gondola with no line, a non-positive `BOARD`/`ALIGHT` amount, a malformed
line), the engine writes a diagnostic to standard error and exits with a nonzero
status without printing a ledger.

# Digests

Every document carries a `digest`: the lowercase hex sha256 of that document's
**payload**. The payload is not the JSON. It is a short tab-separated text built
from the fields listed below, lines joined with `\n`, with a final `\n` after
the last line. `internal/canon` has the helpers: `Field` joins with tabs,
`Payload` joins and terminates, `Digest` hashes. `tools/payload-digest.py` hashes a payload file the same way, for checking by hand.

Fields that appear in the JSON but not in a payload are outside the digest on
purpose — `stats`, `requires` and `required_by` describe how the answer was
reached and what it depends on, and are not part of the answer's identity.

## Lock

```
protocol<TAB>slate/1
project<TAB><project>
allow-yanked<TAB><true|false>
pkg<TAB><name><TAB><version><TAB><true|false><TAB><features joined by ",">
waive<TAB><waiver string>
```

One `pkg` line per package in the lock's order, its fourth field the yanked flag
of the selected release and its fifth the enabled features joined by a comma —
an empty field when the package has none. Then one `waive` line per waiver, in
the lock's order. A lock with no waivers has no `waive` lines.

## Trail

```
protocol<TAB>slate/1
trail<TAB><project>
step<TAB><step><TAB><package><TAB><version><TAB><candidates joined by ",">
```

One `step` line per step, in step order, the candidate versions joined by a
comma in the order the trail lists them.

## Conflict

```
protocol<TAB>slate/1
conflict<TAB><project><TAB><package>
constraint<TAB><requirer><TAB><range>
```

One `constraint` line per constraint, in the document's order.

## Index

```
protocol<TAB>slate/1
index<TAB><project count>
project<TAB><project><TAB><status><TAB><packages><TAB><backtracks><TAB><digest>
```

One `project` line per project, in the document's order, carrying that project's
own digest as the last field. Integers are written as plain decimals.

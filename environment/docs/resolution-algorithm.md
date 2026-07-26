# Resolution

Resolution turns one manifest into one lockfile: at most one version per package
of the dependency closure, chosen from the registry. The procedure below is the
whole contract. It is reproducible, so a second run over the same inputs produces
byte-identical documents, and the trail in
`<out>/staging/<project>.trail.json` shows the order the search actually took —
an assignment that happens to be right but was reached in a different order is
still wrong.

## State

* **Active constraints** — a list of `(requirer, package, range)` triples. The
  requirer is the literal string `root` for a manifest `require` line, and
  `<name>@<version>` for an edge that a selected release brought in. The same
  triple is never added twice; two different requirers asking for the same range
  are two constraints.
* **Requested features** — a set of feature names per package, unioned from
  every requirer that asked for them. A manifest `require` line contributes its
  `+feat` group; a selected release contributes nothing (releases declare
  features, they do not request them).
* **Assignments** — the packages already given a version, in the order they were
  given one.

Start with the manifest: one constraint per `require` line, with the requested
features attached to their package.

## The loop

1. **Done?** If every package that has at least one active constraint is
   assigned, resolution succeeded.
2. **Pick the package.** Among the packages that have an active constraint and
   no assignment, build each candidate list (step 3) and take the package with
   the fewest candidates. Break a tie by package name, ascending.
3. **Build the candidate list.** For package P:
   * If the manifest overrides P, the candidate list is exactly the overridden
     version, whether or not the active constraints admit it and whether or not
     it is yanked. An override for a package that the registry does not publish
     at that version is an input error (exit 4).
   * Otherwise, take the releases of P that satisfy **every** active constraint
     on P. Drop the yanked ones. If that leaves nothing and the manifest sets
     `allow-yanked true`, use the yanked matches instead. Order what remains
     newest first.
   A constraint that names a package the registry does not publish at all is an
   input error (exit 4), not a conflict.
4. **Empty list?** That is a conflict on P. Record it (see *Conflicts*) and
   backtrack.
5. **Assign.** Take the first untried candidate for P. Add the edges of that
   release as active constraints: the `requires` list in registry order, then,
   for each requested feature of P that the release declares, that feature's
   edges — features taken in ascending name order. A requested feature the
   release does not declare adds nothing.
6. **Check.** If a newly added constraint is not satisfied by a package that is
   already assigned, that is a conflict on the already-assigned package: record
   it and backtrack. Overridden packages never conflict; see *Overrides*.
7. Repeat.

## Backtracking

Every assignment sits on a stack together with the remaining candidates from its
candidate list. To backtrack: undo the newest assignment, dropping the
constraints it added, and count one backtrack. If that assignment still has an
untried candidate, continue the loop from step 5 with it; otherwise pop it and
undo the next one, counting another backtrack, until an assignment with an
untried candidate is reached.

Undoing an assignment never rebuilds a candidate list that is already on the
stack: a list is computed once, when its package is picked in step 2, and the
trail reports it as computed then, including the candidates that were tried and
abandoned before the one that stuck.

If the stack empties with no untried candidate anywhere, the manifest is
unsatisfiable.

## Overrides

An override pins a package but does not pull it into the closure: it only takes
effect once some active constraint names that package. The pinned version is
assigned even when it contradicts the constraints on it, and every active
constraint it does not satisfy is waived rather than enforced. Waivers are
collected after resolution succeeds, one string per unsatisfied constraint:

```
<requirer> requires <package> <range>
```

sorted ascending, duplicates removed.

## Conflicts

A conflict records the package it happened on and the active constraints on that
package at that moment. The newest record survives: when a project turns out to
be unsatisfiable, the conflict document reports the last conflict the search saw
before the stack emptied.

## Counters

`assignments` is the number of packages in the finished lock. `backtracks` is
the number of undone assignments, counted as described above — zero when the
first candidate of every package stuck. For an unsatisfiable project,
`backtracks` counts every undo the exhausted search performed.

## What `slate resolve` writes

For `slate resolve <project>`:

| Outcome | Files | Exit |
|---------|-------|------|
| resolved | `<out>/<project>.lock.json`, `<out>/staging/<project>.trail.json` | 0 |
| unsatisfiable | `<out>/<project>.conflict.json` | 3 |

A resolved project must not leave a stale conflict document behind, and an
unsatisfiable one must not leave a stale lock or trail behind: whichever files
the other outcome would have written are removed for that project.

`slate resolve --all` resolves every project under the manifest directory in
ascending name order, writes the same per-project files, and then always writes
`<out>/index.json`. It exits 0 when the index was written, even when some
projects were unsatisfiable — their status is in the index. It exits 4 if an
input was unusable, since then the index would be a lie. Every manifest is parsed
before the first artifact is written, so a batch that exits 4 leaves the output
directory exactly as it found it rather than a partial library.

## Document keys

Full shapes, orderings and types are in `lock-schema.json`. The keys, in the
order each document writes them:

| Document | Keys |
|----------|------|
| lock | `protocol`, `project`, `allow_yanked`, `packages`, `waived`, `stats`, `digest` |
| lock package entry | `name`, `version`, `yanked`, `features`, `requires`, `required_by` |
| stats | `assignments`, `backtracks` |
| trail | `protocol`, `project`, `steps`, `digest` |
| trail step | `step`, `package`, `version`, `candidates` |
| conflict | `protocol`, `project`, `package`, `constraints`, `backtracks`, `digest` |
| conflict constraint | `requirer`, `range` |
| index | `protocol`, `projects`, `digest` |
| index entry | `project`, `status`, `packages`, `backtracks`, `digest` |

`features` holds the feature names requested for that package, ascending.
`requires` holds the edges the selected release contributed, in the order step 5
added them. `required_by` holds the requirer labels of the active constraints on
that package, ascending. `status` is `locked` or `unsatisfiable`. Every
`digest` is the lowercase hex sha256 specified in `digest-spec.md`.

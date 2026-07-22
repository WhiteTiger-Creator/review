# Output contract

For every `CMP <qid> <left> <right>` row, in the order the queries appear within
their scenario and in scenario order, emit exactly one line:

```
<scenario-id>|<qid>|<result>
```

No line is emitted for a `REQUIRE` row. The `<result>` field is one of:

- one of the two candidate version strings, copied verbatim, when the resolver
  installs a build for this query;
- the token `NONE` when the resolver installs neither candidate;
- the token `INCOMPARABLE` when the two candidates do not share an identical
  `major.minor.patch` core.

Nothing else is written to standard output. There is no trailing summary and no
blank separator line between scenarios. Each output line is stripped of
surrounding whitespace and contains exactly two vertical bars.

When the two candidates share a core, which build the resolver installs is
governed by two things: the install-preference ordering of their prerelease
tags — read identifier by identifier from left to right, and *not* always
agreeing with standard version precedence — and the `REQUIRE` requirements in
force at that point in the scenario, which constrain and can accumulate over the
scenario. The precise ordering, the way requirements constrain the choice, and
when the result is `NONE` are the policy this task is about; infer them from the
worked scenarios under `data/examples`, which pair inputs with expected output.

# Output contract

For each scenario, in the order scenarios appear on standard input, emit one
line for every distinct module named by a `QUERY` row in that scenario. Within
a scenario the lines are sorted in ascending lexical order by module name.
Each line has exactly three fields separated by a vertical bar:

```
<scenario-id>|<module>|<version>
```

The `<version>` field is a version string with the leading `v` and three
dot-separated decimal fields, copied in the exact spelling used in the input.
If the queried module has no requirement edge reachable from the main module,
the third field is the literal token `NONE`. If the queried module is reachable
but over-constrained — the version demanded of it exceeds its binding ceiling —
the third field is the literal token `CONFLICT`. A module reachable only through
an over-constrained module is itself `NONE`.

Nothing else is written to standard output. There is no trailing summary, no
header, and no blank separator line between scenarios or between lines.

# Registry and manifest formats

## Registry files

One JSON file per package, named `<package>.json`. The `name` field must equal
the file stem. Releases may appear in any order in the file; ingest sorts them
newest first before anything else looks at them.

```json
{
  "name": "chert",
  "releases": [
    {
      "version": "1.5.0",
      "yanked": false,
      "requires": [{"name": "basalt", "range": "^2.2.0"}],
      "features": {"trace": [{"name": "tuff", "range": "^0.4.0"}]}
    }
  ]
}
```

* `version` — the version grammar in `constraint-grammar.md`. Versions are
  unique within a file.
* `yanked` — the release was withdrawn. See the yank rule in
  `resolution-algorithm.md`.
* `requires` — edges every consumer of the release gets. May be absent or empty.
* `features` — extra edges that only apply when the named feature is enabled.
  May be absent.

A registry file that breaks any of the above is an input error: the tool prints
one line to standard error and exits 4. It is never treated as an empty package.

## Manifest files

One file per project, named `<project>.slate`, line oriented. Blank lines and
lines starting with `#` are ignored. The `project` name must equal the file stem.

```
project kilnworks
require dolomite ^3.0.0
require chert ^1.5.0 +trace
require quartz >=2.0.0 <3.0.0 +simd,audit
override basalt 1.9.0
allow-yanked true
```

| Directive | Rule |
|-----------|------|
| `project <name>` | exactly one per file |
| `require <name> <range> [+feat,feat]` | at least one per file; a package may be required once |
| `override <name> <version>` | optional, repeatable, one line per package |
| `allow-yanked true\|false` | optional, defaults to `false` |

The shipped library is crucible, driftworks, emberyard, foundry, kilnworks,
rampart and slagworks. Each one exercises a different corner of the rules, and
emberyard is there because a project is allowed to have no solution at all.

The range is everything between the package name and the optional feature
group, so a two-bound range keeps its space. The feature group is a single
token starting with `+`; feature names are comma separated and are sorted
ascending when the manifest is parsed.

Anything else — an unknown directive, a repeated `project`, a package required
twice, a stem that disagrees with the `project` line — is an input error and
exits 4.

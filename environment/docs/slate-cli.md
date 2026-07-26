# slate CLI

`slate` is the offline registry tool under `/app`. It reads a registry directory
and a manifest directory and writes documents into an output directory. Nothing
it does touches the network.

## Directory overrides

Every subcommand accepts the same three overrides, in `--flag VALUE` or
`--flag=VALUE` form, anywhere on the command line:

| Flag | Default | Holds |
|------|---------|-------|
| `--registry` | `/app/registry` | one `<package>.json` file per package |
| `--manifests` | `/app/manifests` | one `<project>.slate` file per project |
| `--out` | `/app/out` | documents the tool writes |

The overrides exist so a registry can be inspected or resolved from a copy
without touching the shipped one. A subcommand that writes files must honour
`--out` for every file it writes, including the staging directory.

## Subcommands

```
slate show <package>              print a package, its releases and its edges
slate versions <package>          list versions newest first, yanked ones marked
slate manifest <project>          print the parsed manifest as canonical JSON
slate manifest <project> --export write <out>/staging/<project>.manifest.json
slate audit                       print registry totals
slate audit <project> [--flat]    print the legacy closure estimate
slate version                     print the tool version and resolver constants
slate resolve <project>           lock one project (not implemented yet)
slate resolve --all               lock every project and write the index
```

`slate resolve` is the subcommand this image does not have yet. Its outputs and
exit codes are specified in `resolution-algorithm.md` and `lock-schema.json`;
everything on this page applies to it as well.

`<project>` and `--all` are the two forms of `resolve`, never both at once:
`resolve` takes exactly one positional project name, or `--all` and no
positional at all. `resolve <project> --all` and `resolve --all <project>` are
both a command-line error (exit 2), not `--all` overriding or being overridden
by the name — the same as calling `resolve` with two project names.

`slate version` prints four lines: the tool version, the resolver protocol tag
carried by every document, the digest algorithm, and the lock schema number.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | the subcommand finished and wrote what it promised |
| 2 | the command line is wrong: unknown subcommand, missing argument, unknown flag |
| 3 | resolution failed because no assignment satisfies the manifest |
| 4 | an input is unusable: registry file, manifest file, or a missing package |

Harnesses that grade this image stage their own registry and manifest
directories outside `/app`, name that location in `TB3_SLATE_FIXTURES`, and pass
it through the overrides above, so every subcommand has to work against
directories it has never seen.

Every error goes to standard error on a single line prefixed `slate: `, and
standard output stays empty. Exit 2 adds the usage block after that line, since
the caller needs to see the subcommand list. Nothing that exits non-zero leaves a
half-written document behind: a run that cannot use its input writes nothing at
all, and a run that resolves part of a library before hitting a bad manifest is
not allowed either — see the batch rule in `resolution-algorithm.md`.

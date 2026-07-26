/app holds slate, the read-only front end for the package registry a build team keeps offline as JSON files. It can already print a package with its releases and edges, list versions newest first, echo back a parsed project manifest, and total up the registry. Planning a build is the one thing it cannot do: nothing here walks the dependency edges and turns a manifest into a lockfile of pinned versions, so every project is assembled by hand and no artifact says what went into it.

Your job is to give slate a resolve subcommand that produces those artifacts.

Running slate resolve with a project name picks one version per package for that project — honouring the ranges every selected release declares, the features the manifest switches on, the pins it forces and its policy on withdrawn releases — then publishes the lockfile /app/out/<project>.lock.json together with the search walk in /app/out/staging/<project>.trail.json. Where no assignment exists it writes /app/out/<project>.conflict.json and exits 3 instead.

Running slate resolve --all does the same for every project in /app/manifests and finishes by writing the ladder over the whole library, /app/out/index.json.

Four contracts decide what counts as correct:

/app/docs/resolution-algorithm.md is the one that matters most — which package the search picks next, in which order candidates are tried, how a retreat is counted, and which artifacts each outcome leaves behind.

/app/docs/constraint-grammar.md covers version ordering, the five range forms, and the rule that keeps release candidates out of sight.

/app/docs/registry-format.md covers the package files and the manifest directives, and what makes either one unusable.

/app/docs/digest-spec.md gives the tab-separated payload behind every fingerprint field, byte for byte.

Flags, exit codes and the shape of each artifact are in /app/docs/slate-cli.md and /app/docs/lock-schema.json.

Resolution has to be reproducible: the same inputs give the same bytes on every run. Two assignments can both honour every range without both being the answer, and an artifact only counts when the fingerprint it carries agrees with what that same artifact publishes.

Code sits in /app/cmd and /app/internal. The module compiles with make all from /app, and packages you add under /app/internal need no Makefile edit. Leave a working /app/bin/slate behind.

The browsing commands — show, versions, manifest, audit, version — must answer exactly as they answer now, the directory overrides must keep working everywhere, and nothing under /app/registry or /app/manifests may change.

Nothing in this image reaches the network. Finish by running slate resolve --all, so /app/out carries a lock or a conflict for every project plus the ladder.

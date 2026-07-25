# Versions and ranges

## Version grammar

`MAJOR.MINOR.PATCH`, three decimal numbers, with an optional prerelease marker
`-rc.N` where N is 1 or greater. `2.3.0` and `1.0.0-rc.2` are both versions;
`1.0` and `1.0.0-beta` are not.

Ordering compares major, then minor, then patch. When the three fields are
equal, a release sorts **after** every prerelease that shares them, and
prereleases sort among themselves by N:

```
0.9.3 < 1.0.0-rc.1 < 1.0.0-rc.2 < 1.0.0 < 1.0.1
```

`internal/semver` already implements this ordering; `slate versions` prints it.

## Range grammar

A range is one of these five forms. Nothing else is a range, and a range that
does not parse is an input error (exit 4).

| Form | Matches |
|------|---------|
| `*` | every version |
| `=X.Y.Z` | that one version, written exactly, prerelease marker included |
| `^X.Y.Z` | the compatible span, below |
| `~X.Y.Z` | `>= X.Y.Z` and `< X.(Y+1).0` |
| `>=A <B` | `>= A` and `< B`, one space between the bounds |

The caret span depends on the leading non-zero field, the usual rule for
registries where a zero major is not stable yet:

| Range | Span |
|-------|------|
| `^2.3.0` | `>= 2.3.0`, `< 3.0.0` |
| `^0.4.0` | `>= 0.4.0`, `< 0.5.0` |
| `^0.0.7` | `>= 0.0.7`, `< 0.0.8` |

## Prereleases in ranges

A prerelease version is invisible to a range unless the range text asks for one.
Precisely: a range admits a prerelease `V` only when the range text contains a
version literal that carries an `-rc.` marker and whose major, minor and patch
equal those of `V`. When the range admits it, the ordinary bound comparison then
decides, using the ordering above.

So `^1.0.0-rc.1` matches `1.0.0-rc.1`, `1.0.0-rc.2`, `1.0.0` and `1.4.2`, while
`>=0.9.0 <2.0.0` matches none of the `1.0.0-rc.*` releases even though they sit
inside the bounds. `=1.0.0-rc.2` matches exactly that prerelease.

Because a candidate has to satisfy **every** active range on its package at
once, one plain range anywhere in the graph is enough to keep prereleases out of
that package's candidate list.

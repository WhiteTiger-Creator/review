# The casebook: inputs, invocation, and reports

## The openings folder

The openings under study live one per file in the openings folder (mounted at
`/app/openings/`). Each file is a JSON object with two members:

- `id` — a non-empty string naming the opening; ids are unique across the folder.
- `heaps` — a non-empty list of integers, each at least `1`, giving the heap sizes
  of the opening in any order.

A file that is not valid JSON, is missing either member, carries a wrong type, has
an empty `id`, has an empty `heaps` list, contains a heap size below `1`, or
repeats an `id` already seen is a malformed opening. The openings folder is a
read-only source and is not modified.

Only regular files whose name ends in `.json`, sitting directly in the openings
folder, are read as openings. Any other entry — a nested subdirectory, or a file
with a different extension — is skipped rather than treated as malformed, and
does not become an opening. When the folder contains no such file, there are
simply no openings to study.

## Invocation

The program is a C++17 build at `/app/build/redeal`, produced from sources under
`/app/src/`. It takes exactly two positional arguments, `<openings_dir>` and
`<out_dir>`, in that order; both must already exist and be directories. It exits
with status `0` once both reports have been written into `<out_dir>`, overwriting
any file of the same name already there. It exits with a non-zero status when it
is given the wrong number of arguments, when the first or second path is missing
or is not a directory, or when any opening is malformed; the reports are written
only after every opening has been read cleanly.

## The two reports

Both reports are written into `<out_dir>`.

### `openings.json`

```
{
  "openings": [
    {
      "arrivals": <int>,
      "counters": <int>,
      "endgame": [[<int>, ...], ...],
      "endgame_length": <int>,
      "heaps": [<int>, ...],
      "id": <str>,
      "reachable": <bool>,
      "redeals_to_endgame": <int>
    },
    ...
  ]
}
```

One record per opening, the list ordered by `id` ascending. `heaps` is the
opening's position in canonical (non-increasing) form and `counters` is their sum.
`endgame` is an ordered list of positions (each a list of heap sizes). The
remaining members are defined in `studying-openings.md`.

### `sizes.json`

```
{
  "sizes": [
    {
      "endgames": [{"cycle": [[<int>, ...], ...], "length": <int>}, ...],
      "longest_settling": <int>,
      "positions": <int>,
      "size": <int>,
      "unreachable_positions": <int>
    },
    ...
  ]
}
```

One record per distinct counter total among the openings, the list ordered by
`size` ascending. Inside `endgames`, each entry pairs a `cycle` (the endgame as an
ordered list of positions) with its `length`, and the entries are ordered by their
smallest position. The members are defined in `studying-sizes.md`.

## Formatting

Every report is UTF-8, ASCII-only, indented two spaces, with object keys sorted
lexicographically at every depth and a single trailing newline. Integers stay
integers and booleans stay booleans. The order of items inside the `openings`,
`sizes`, `endgame`, `endgames`, `cycle`, and `heaps` lists is the order defined
above and in `positions-and-order.md`, not key order. An endgame position list and
a heap list are never empty; the two top-level lists are `[]` if there were no
openings.

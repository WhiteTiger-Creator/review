# handsettle

Settlement tool for the club scoreboard. It reads a night's hand log and reports, for each
finished hand, what the winner scored and what the table pays.

## Build and run

```
make
./handsettle examples/hands.json
```

The report is a JSON array on stdout, one object per hand in log order:

```
[
 {
  "id": "e0001",
  "scored": true,
  "han": 2,
  "fu": 40,
  "yaku": ["Tanyao", "Dora 1"],
  "payment": {"main": 2600, "additional": 0, "mainBonus": 0,
              "additionalBonus": 0, "riichiSticks": 0, "total": 2600}
 }
]
```

Hands that hold no yaku come back with `"scored": false`.

## Layout

`cmd/handsettle` is the entry point, `internal/tiles` handles notation and `internal/table`
holds the log and report shapes. The settlement itself lives in `internal/settle`.

`docs/scoring-rules.md` is the reference for notation, the report format, the yaku names we
print and the house rules our table plays under. `examples/` has 82 worked hands with the
settlement the club engine recorded for each; `make test` replays them.

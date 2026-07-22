# Case files

`data/` holds every public case file, named `case_*.txt`. There may be more
cases here than any single family name suggests; treat every file matching
`data/case_*.txt` as a case to handle correctly, not a fixed enumerated
list. Case files range from small hand-checkable matrices up to `16 x 10`,
with complex matrix entries and conditioning that vary considerably from
one file to the next. `data/case_toy2x2.txt` is a tiny hand-checkable
fixture used by `smoke_test`.

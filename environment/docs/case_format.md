# Case input

Each JSON case under `/app/environment/fixtures` includes a string `name`, a `nodes` array, and an optional `marks` string array.

Each node object must include string `id` and numeric `features` array.

The replay script reads one case path and emits `/app/output/culvert_rank.yaml`.

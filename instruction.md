The storage hosts in this estate run a snapshot reclaim supervisor: a fixed, fully deterministic component that decides which snapshots a pool keeps and which it releases when the pool is short of free space. The component is gone from these hosts and the operator manual it was written against is all that survives. Restore it so the hosts report exactly what the supervisor reported.

`/app/PROTOCOL.md` is that operator manual and it is the whole contract. It covers the pool record and its extents, the anchors that are always kept, the four retention tiers and how their keep counts are spent, how a released set frees shared blocks, the reclaim ladder the supervisor walks when a pool is short of its target, the report schema, and the two digests. `/app/samples/` holds six recorded pool records beside the report the supervisor produced for each, so every rule in the manual can be checked against a worked example.

`/app/cmd/reclaim/main.go` is an empty skeleton. Deliver an executable at `/app/reclaim`, compiled from the `./cmd/reclaim` package, that runs as `reclaim plan --pools <jsonl> --out <json>`, reads one pool record per line, and writes the report the manual describes. Add whatever Go packages you need under the `reclaim` module.

`/app/PROTOCOL.md` and `/app/samples/` are read-only. A fatal input error exits nonzero and writes no output file.

Grading replays the recorded samples and feeds held-out pools of the same shape, checking every field of every pool row and both digests. A pool is scored as a whole, so a supervisor that gets one rule wrong still scores zero on every pool that rule touches.

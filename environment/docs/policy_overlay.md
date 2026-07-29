# Policy overlay selection

## Overlay JSON (`pack/policy/ov_gN.json`)

| field | type | notes |
|-------|------|-------|
| gen | integer | overlay generation identity |
| shadow_radius | integer | suppression distance threshold for include and exclude mask overlap |
| policy_id | string | stable overlay identifier |

Filenames follow `ov_g{N}.json` where N is the overlay generation.

## Tip selection

Active generation is the largest `gen` among records in `/app/environment/pack/ledger/waves.ndjson` whose `tomb` field is false. Tombstoned records must not advance tip.

## Overlay pick

Load `pack/policy/ov_g{N}.json` where N is the active tip generation.

## Durable epoch bus (`pack/seed/.epoch_bus.json`)

| field | type | notes |
|-------|------|-------|
| token | unsigned integer | hit-cache identity; must bump on scrub invalidate and preserve restore, and on tip bind |
| bound_gen | integer | gen-bound checkpoint index used for hot staging; must equal ledger tip after successful tip/policy bind |
| storm_ok | boolean | true only when storm generation is clear for emit |
| rev | unsigned integer | monotonic bus revision |

After a successful tip-resolved grid-full run, observables on the bus are `bound_gen` equal to tip T, `storm_ok` true when `.storm_gen` parses as decimal 0, and a `token` that advanced across scrub invalidate and preserve restore. Emit stays refused while `bound_gen` disagrees with tip, `storm_ok` is false, or `.storm_gen` is non-zero. Bare scrub runs epochctl invalidate. Preserve-anchor runs epochctl restore.

## Probe install surface

Offline package probes install a temporary active overlay without reading the tip file. The policy package must export `InstallForProbe(ov Overlay)` which sets the in-process active overlay to the supplied `Overlay` value (`Gen`, `ShadowRadius`, `PolicyID`, `Path`). After install, `ActiveRadius`, `ActiveGen`, `ActiveID`, and `ActivePath` must reflect that overlay. Graph shadow suppression and other readers that consult the live overlay must observe the installed radius on the next `Run`. Tip-driven `Run(tipGen)` remains the production path and must still select `ov_g{N}.json` for tip N. Ranking probes that install policy id or path `probe` read gen-bound staging from the probe overlay generation rather than the durable bus bound generation.

## Shadow suppression (uses active overlay)

The active overlay `shadow_radius` is the distance threshold R. Suppress an include arm when an exclude arm with non-zero `shadow_link` shares a mask bit and `abs(id - link)` meets or exceeds R (id is the include arm id; link is that exclude arm shadow_link). Process exclude arms in ascending `Seq` before collecting include arms into the active set. Graph packages must read the live overlay radius from the selected overlay.

## Hit cache

Cache identity covers family, selected overlay generation, shadow epoch, cell layout dimensions, a signature over incident field bytes, and the durable epoch-bus token. After a successful tally, the burst grid cache epoch must match its shadow epoch.

## lane_order

Rank by descending hit score, then by descending staged-anchor byte at arm_id modulo 8, then by ascending arm id, capped by the profile budget. Staged-anchor bytes for production ranking come from the gen-bound checkpoint `pack/checkpoints/stg_g{N}.bin` when present for the epoch-bus bound generation N; otherwise from `.anchor_staging`.

## Digests and n3_v1

Cold digests use the first eight bytes of `token_seed.bin`. Hot digests use the staging bytes that fed lane ranking. Converged rows require the three digest columns to match. Emitting n3_v1 requires `.storm_gen` to parse as decimal 0 and a tip-coherent epoch bus. After preserve-anchor, tip, staging, storm_gen, and the epoch bus must be coherent again.

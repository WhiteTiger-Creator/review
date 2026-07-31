# Rack maintenance change-control runbook

`drainwave` is the host-side control used by rack operations to turn the live fleet inventory and an approved change policy into one canonical maintenance-window plan. It creates missing output parent directories, replaces the output atomically, and is silent on stdout when successful.

## Input

The inventory is an object containing only `nodes`. `nodes` has 1 through 256 objects, each containing exactly `id`, `zone`, `rack`, `power`, and `services`. IDs, zones, racks, and service names are non-empty strings. Node IDs are distinct. `power` is an integer from 1 through 1,000,000. `services` has 1 through 32 distinct names.

The policy contains exactly these fields:

- `targets`: 1 through 12 distinct existing node IDs. The full range is operational: a valid 12-target request must be planned with the same exact objective, not rejected or approximated.
- `min_available`, `zone_parallel`, and `rack_power_limit`: maps with non-empty keys and integer values from 0 through 1,000,000. Every zone and rack used by a target appears in its corresponding limit map.
- `cooldown`: a map of at most 16 service names to integer values from 0 through 3.
- `precedence`: an array of distinct two-string arrays `[before, after]`. Both IDs are targets and differ.
- `cohorts`: an array of target-ID arrays. Each cohort has 2 through 4 distinct members, and no target belongs to more than one cohort.
- `separation`: an array of objects containing exactly `left`, `right`, and `gap`. The two IDs are distinct targets, `gap` is an integer from 0 through 3, and an unordered target pair appears at most once.
- `rolling_limits`: a map of at most 16 service names to objects containing exactly `window` and `max_unavailable`. `window` is an integer from 1 through 4 and `max_unavailable` is an integer from 0 through 1,000,000.
- `risk_weights`: a map of at most 16 service names to integer weights from 1 through 1,000.
- `max_wave_size`: an integer from 1 through the target count.

All collection fields are required even when empty. Unknown fields, trailing JSON, wrong JSON types, empty names, duplicate values, overlapping cohorts, duplicate directed precedence edges, duplicate unordered separation pairs, missing target zone/rack limits, out-of-range integers, and bad references are invalid. A precedence cycle, an oversized cohort, or mutually incompatible valid rules are not malformed input; they may make the request unsatisfiable.

## Scheduling

A launch wave drains all of its nodes simultaneously. They return before the next wave. Every target appears in exactly one non-empty wave, and a wave contains no more than `max_wave_size` nodes.

A candidate wave is legal only when all of these hold:

- A cohort is either wholly present or wholly absent.
- Every selected node's precedence predecessors were completed in earlier waves.
- The selected count for each zone is no greater than `zone_parallel[zone]`.
- The selected power sum for each rack is no greater than `rack_power_limit[rack]`.
- For every `min_available` service, the inventory total minus the selected replica count is at least the configured minimum.
- A selected node does not carry a service whose cooldown counter is positive at the start of the wave.
- Separation endpoints are not in the same wave. If one endpoint was drained earlier, at least `gap` complete launch waves occur between the endpoint waves. For example, `gap: 1` permits waves 1 and 3 but not waves 1 and 2. Idle waves cannot be invented.
- For every rolling limit, the selected replica count plus the counts in the preceding `window - 1` waves is no greater than `max_unavailable`. Missing earlier waves count as zero.

After a wave, existing positive cooldown counters decrease by one. Then each selected service present in `cooldown` raises its counter to at least that service's configured value.

For a wave, let `count(service)` be the selected replica count. Its risk is the sum, over every `risk_weights` entry, of `weight * count(service) * count(service)`. Schedule risk is the sum of wave risks. Choose a plan by these priorities, in order:

1. fewest waves;
2. lowest schedule risk;
3. lexicographically smallest array of wave arrays after sorting node IDs by Unicode code point inside every wave.

For the final comparison, compare waves in order and node strings in order; when one wave is a prefix of another, the shorter wave is smaller.

## Output

A successful plan is compact JSON followed by one newline:

```json
{"status":"ok","wave_count":3,"schedule_risk":12,"plan_digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","waves":[{"wave":1,"nodes":["node-a"],"unavailable_services":{"api":1},"zone_counts":{"east":1},"rack_power":{"r1":4},"cooldown_after":{"api":1},"rolling_unavailable":{"api":1},"wave_risk":3}]}
```

`waves` contains every wave in order. `wave` is its one-based index and `nodes` is sorted. `unavailable_services` contains every `min_available` key, including zero counts. `zone_counts` and `rack_power` contain exactly the zones and racks represented in that wave. `cooldown_after` contains every `cooldown` key. `rolling_unavailable` contains every `rolling_limits` key and the rolling count ending at that wave. `wave_risk` and top-level `schedule_risk` are JSON integers.

`plan_digest` is `sha256:` plus the lowercase SHA-256 hex digest of this UTF-8 transcript, one line per wave:

`<wave>|<comma-joined nodes>|<unavailable key=value pairs>|<zone key=value pairs>|<rack key=value pairs>|<cooldown key=value pairs>|<rolling key=value pairs>|<wave_risk>\n`

Map pairs are sorted by key and comma-joined. An empty map contributes an empty field. JSON object key order is irrelevant.

If no schedule exists, write exactly `{"status":"unsatisfiable","reason":"no_valid_schedule"}` plus a newline and exit 3. A valid schedule exits 0. Invalid arguments or input exit 2 with the single stderr line `drainwave: invalid input`. Read or write failures exit 1 with `drainwave: io error`. On exit 1 or 2, do not create or alter the output file.

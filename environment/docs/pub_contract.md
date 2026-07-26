# Public contract

## Commands
Work inside `/app/environment` and run this pair in order.
1. `npx tsx /app/environment/run_fit/main.ts`
2. `npx tsx /app/environment/run_cf/main.ts --verify /app/output/cf_trace.json`

## L0 cardinality
At most three raw cell mutations per counterfactual row (field max_l0 is three). Field l0 counts those mutations and must stay within that cap.

## Serialized size limit
UTF-8 length of the compact JSON serialization of encoded vector v is at most two hundred twenty (field max_n is two hundred twenty). Field nbytes records that length.

## Flip-rate floor
After the counterfactual check, `/app/output/scorecard.json` field flip_rate is at least fifty-five hundredths on the secondary union (`data/blank_rows.csv` then `data/novel_rows.csv`). Compute flip_rate as the count of cf_trace.json rows where y1 differs from y0 and l0 is positive, divided by n_rows. Compute mean_l0 as the mean of l0 over those successful rows (zero when none succeed). n_rows equals the secondary union size (at least 40). Reported flip_rate and mean_l0 must match those definitions exactly.

## Fit accuracy floor
After fit, scorecard.json field acc is at least seventy hundredths on primary labeled rows in `data/prime_batch.csv` (positive when score probability is at least one half).

## Artifacts under `/app/output/`
### layout.json
Feature layout. Fields include string tag, integer dim, integers r0 and r1, object offs with integer keys g, t, nx, object vocab with sorted unique string lists g and t, float scale, integers max_l0 and max_n.
tag, dim, r0, r1, offs, scale, max_l0, and max_n come from `fixtures/seed_layout.json` unless fit rewrites them. vocab.g and vocab.t list every non-empty grp and tier string on the primary CSV, sorted ascending. r0 and r1 are distinct integers from zero inclusive through dim exclusive.

### bundle.json
Weight bundle. Fields include float list w (length dim) and float b.

### scorecard.json
Fields include float acc, float flip_rate, float mean_l0, and integer n_rows.

### cf_trace.json
Top-level object has rows. Each row has string id, integers y0 and y1, array mut of objects with keys k, a, and b where k is one of grp, tier, or mag, integer l0, integer nbytes, and string enc_digest.
Row order matches blank_rows.csv then novel_rows.csv (header skipped).
enc_digest is lowercase hex of FNV-1a sixty-four-bit over UTF-8 bytes of encoded v entries joined by commas with three decimal places (example values like zero-point-zero zero-zero).
A successful counterfactual has y1 differing from y0, l0 between one and max_l0 inclusive, nbytes within max_n, and an encoding that respects the fitted layout (blank cells use reserved slot r0, tokens absent from fitted vocab use reserved slot r1).

## Vector identity
Blank grp and tier cells land on reserved slot r0. Tokens absent from fitted vocab lists land on reserved slot r1. Known tokens use typed offset slots under offs.

## Inputs
| Path | Role |
|------|------|
| `data/prime_batch.csv` | Primary labeled rows for fit |
| `data/blank_rows.csv` | Secondary rows with blank cells |
| `data/novel_rows.csv` | Secondary rows with tokens absent from the primary set |
| `fixtures/seed_layout.json` | Seed layout constants |

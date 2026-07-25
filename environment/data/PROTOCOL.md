# Operating-characteristic protocol specification

This document fixes every rule the reported numbers depend on. Where a rule could
be read two ways, the reading stated here is the one that applies.

## 1. Input

`/app/data/sensors.csv`, one row per observation, comma separated, with a header.

| column | type | role |
|---|---|---|
| `id` | integer | record identifier, not used in the analysis |
| `Temperature` | real | ambient temperature, not used |
| `Humidity` | real | relative humidity, not used |
| `Light` | real | illumination, not used |
| `CO2` | real | the score under study |
| `HumidityRatio` | real | derived humidity, not used |
| `Occupancy` | integer | the outcome, 1 for occupied and 0 for empty |

The score is `CO2`. The outcome is `Occupancy`. A larger score is taken to
indicate a greater tendency toward the positive outcome. Let the number of
positive rows be `P` and the number of negative rows be `N`.

## 2. Ranking and area under the curve

Rank all rows by score, smallest first. Rows sharing a score receive the average
of the ranks they occupy, so a group of tied rows all take the mean of their
positions. Let the rank sum of the positive rows be `Rp`, with ranks counted
from 1. The area under the curve is `Rp` minus `P * (P + 1) / 2`, all divided by
`P * N`. Tied scores must contribute through the average-rank convention; a rule
that breaks ties arbitrarily reports a different area.

## 3. Operating-point table

The candidate thresholds are the distinct score values. A row is classified
positive when its score is greater than or equal to the threshold, and negative
otherwise. For each threshold record the true-positive count, the false-positive
count, the true-negative count, and the false-negative count, together with the
true-positive rate, which is true positives over `P`, and the false-positive
rate, which is false positives over `N`.

## 4. Standardised partial area

Consider the region of the curve where the false-positive rate lies between 0 and
0.1 inclusive. Trace the curve from a false-positive rate of 0, taking the
operating points in order of increasing false-positive rate, and where the curve
crosses the bound 0.1 between two operating points, add the point that lies
exactly on the bound by linear interpolation of the true-positive rate. The raw
partial area is the area under the traced curve over that region. The standardised
partial area is one half of one plus the raw area minus its minimum possible value
all divided by the range of possible values, where over a false-positive-rate
width `f` the minimum possible area is `f * f / 2` and the maximum is `f`.

## 5. Fixed-sensitivity operating point

Among the thresholds whose true-positive rate is at least 0.95, select the one
whose false-positive rate is smallest. When several share the smallest
false-positive rate, take the largest threshold among them. Report that
threshold and its four confusion counts, its true-positive rate, its
false-positive rate, its precision, which is true positives over predicted
positives, and its F1 score, which is twice precision times recall over their
sum, recall being the true-positive rate.

## 6. Outputs

Write two files to `/app/outputs/`. Real numbers carry 6 decimal places. Integer
fields are compared exactly.

### `roc_points.csv`

Header `threshold,tp,fp,tn,fn,tpr,fpr`. One row per candidate threshold, sorted by
threshold ascending.

### `metrics.json`

An object with keys `n_pos` (integer), `n_neg` (integer), `auc` (real),
`partial_auc_raw` (real), `partial_auc_standardized` (real), `fpr_bound` (real,
0.1), `sensitivity_target` (real, 0.95), and `operating_point`, an object with
keys `threshold` (real), `tp` (integer), `fp` (integer), `tn` (integer), `fn`
(integer), `tpr` (real), `fpr` (real), `precision` (real), `f1` (real).

## 7. Re-runnability

The program must be re-runnable as `bash /app/run.sh` with no arguments. That
command reads `/app/data/sensors.csv`, applies this protocol, and rewrites the
two files in `/app/outputs/`. The assessment reruns that command against other
files placed at `/app/data/sensors.csv` that follow the schema in section 1 but
hold different records, so the protocol has to be applied to whatever data is
present rather than to remembered results.

## 8. Determinism

No network is available. Nothing outside `/app/data` may be consulted. Running
the program twice on the same input must produce byte-identical outputs.

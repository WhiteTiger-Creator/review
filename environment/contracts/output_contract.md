# Output contract

Write two files to `/app/environment/outputs`. UTF-8, comma-delimited, header
row, no index column. Every value in metrics.json is a quoted string.

## predictions.csv

Header `row_id,pred_proba`. One row for every unscored session (every row whose
`target` is blank in the data file), sorted ascending by `row_id`.

| column | type | rule |
|---|---|---|
| `row_id` | int | the `row_id` of an unscored peak-season session |
| `pred_proba` | float | predicted probability that target = 1, in [0, 1] |

Every unscored record must appear exactly once, and these are the only two
columns.

## metrics.json

A flat JSON object with exactly these keys, each a quoted string.

| key | type | rule |
|---|---|---|
| `n_train` | int | number of rows with a non-blank `target` |
| `n_pilot` | int | number of labeled target-domain (pilot) rows |
| `n_test` | int | number of unscored rows |
| `n_test_low` | int | unscored rows in the low band (`ProductRelated <= 7`) |
| `n_test_med` | int | unscored rows in the med band (`8 <= ProductRelated <= 20`) |
| `n_test_high` | int | unscored rows in the high band (`ProductRelated >= 21`) |
| `n_bands` | int | number of engagement bands handled (3) |

`n_test_low + n_test_med + n_test_high` must equal `n_test`.

## Grading

The engagement bands are low (`ProductRelated <= 7`), med (`8 <= ProductRelated
<= 20`) and high (`ProductRelated >= 21`), assigned from the data file. From
predictions.csv and the withheld labels the verifier recomputes held-out ROC-AUC,
PR-AUC and Brier score, globally and within each band, and compares them against a
reference gradient-boosted model refit on the active data file.

These are the acceptance thresholds applied to your predictions:

| check | threshold |
|---|---|
| global ROC-AUC | no more than **0.015** below the reference's ROC-AUC |
| global PR-AUC | no more than **0.060** below the reference's PR-AUC |
| global Brier score | no worse than the reference's Brier score |
| per-band ROC-AUC (each band) | no more than **0.060** below the reference's ROC-AUC for that band |
| per-band calibration-in-the-large (each band) | mean predicted probability within **0.09** of that band's realized (held-out) purchase rate |
| overall calibration-in-the-large | mean predicted probability over all unscored rows within **0.04** of the overall realized purchase rate |

The reported per-band unscored counts must match the data. Every check is repeated
after the verifier re-fits and re-scores your script on several deterministic
variants of the data (including a source-composition skew and subsampled,
jittered resamples), with the reference recomputed on each variant, so the
pipeline must derive everything from the data file it reads.

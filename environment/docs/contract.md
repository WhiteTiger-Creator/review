The bundle selected by `WL_DATA_DIR` contains five CSV relations.

`features.csv` has unique `observation_id`, `partition`, and numeric columns `f1` through `f10`. Partition is `train` or `query`.

`anchors.csv` has unique `observation_id,canonical_class` pairs for a subset of train observations.

`annotations.csv` has unique `observation_id,worker_id,local_symbol` triples. Rows refer only to train observations. A missing worker-observation pair is an abstention and supplies no evidence.

`vocabularies.csv` has `worker_id,local_symbol`. Each worker has exactly six distinct local symbols. For each worker, those symbols have an unknown one-to-one correspondence with the six rows in `classes.csv`. Correspondences differ between workers and bundles. Workers have different error rates. An incorrect report may use any other symbol in that worker's vocabulary.

The analysis reads `WL_DATA_DIR` and writes one CSV to `WL_OUTPUT_PATH`. Its header is:

`observation_id,predicted_class,prob_A,prob_F,prob_E,prob_I,prob_X,prob_H`

The output contains exactly one row per query observation and no train rows. `predicted_class` is one of `A,F,E,I,X,H`. Each probability is finite and nonnegative, and every row sums to one within `1e-6`. `predicted_class` is the class with greatest reported probability; ties follow the class order in `classes.csv`.

Evaluation fits separately on every bundle. Canonical query labels are withheld. The predictive metrics are class-balanced accuracy and clipped multiclass log loss. Input row order and a consistent renaming of one worker's complete private vocabulary do not change the learning problem.

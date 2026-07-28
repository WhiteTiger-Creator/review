# TrustLoom ALS handbook (ops)

## 2. Draft — do not use for acceptance

Lab notebook still says: user-then-item Hu order, constant lambda, fade=1,
colon hash separators, linear confidence 1+alpha*r, keep every ID, fold
bucket `(u+i)%4`, score damping with gamma=3 on diagnostics mean_abs_score,
skip Cholesky jitter, full item replacement (no residual blend), no
confidence ceiling, and rank over all catalog items including train
neighbors. That path was never certified.

## 3.1 Final

TrustLoom production fitting is closed-form alternating least squares with
confidence-weighted observations. Rebuild from `/opt/trustloom` with
`make clean all`. Path flags only; hyperparameters and schedule details are
locked by the model card and its errata. Ranking on holdout is
macro-averaged over eligible users at k=3. Always emit diagnostics.json and folds.json.

If this handbook disagrees with `/app/model-card/trustloom-spec.txt` or
any errata file, the model card and errata win.

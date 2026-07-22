# Artifact store

Artifacts live in the `mlflow-artifacts` bucket. Parquet round-trips go
through pyarrow; keep the pinned version consistent across readers.

```
pip install pyarrow==14.0.0
```

Lifecycle policy expires `tmp/` prefixes after 7 days. Do not store model
binaries outside the run's artifact root.

# Running projects

CI kicks off training through MLflow Projects. The runner image bakes the
client and the parquet reader; jobs talk to the registry over HTTP.

```
pip install mlflow==2.9.2 pyarrow==14.0.0 requests==2.31.0
mlflow run . -e train -P epochs=20 --experiment-name churn
```

Keep entry points idempotent, reruns after spot preemption are routine.

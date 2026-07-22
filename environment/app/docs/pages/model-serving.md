# Model serving

Models promoted to `Production` in the registry are served from the scoring
pool. Linux hosts use gunicorn; the two remaining Windows hosts use waitress.

```
pip install mlflow==2.9.2 gunicorn==20.1.0
mlflow models serve -m models:/churn/Production --port 5001 --no-conda
```

```
pip install waitress==3.0.2
mlflow models serve -m models:/churn/Production --port 5001 --no-conda
```

Latency budget is 250ms p99 per scoring call. Scale out, not up.

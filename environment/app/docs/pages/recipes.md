# Recipes pipeline

The recipes stack was upgraded ahead of the rest of the fleet during the Q1
template rework. Templates render through jinja2.

```
pip install mlflow==2.11.3 jinja2==3.1.2
mlflow recipes run --profile databricks
```

Card artifacts land under `steps/` in the run's artifact root.

# Tracking server deployment

Run the tracking server behind gunicorn on the shared VM. The backend store
is the postgres instance in the ops subnet; the artifact root stays on NFS.

```
python -m venv /srv/mlflow/venv
/srv/mlflow/venv/bin/pip install mlflow==2.9.2 gunicorn==20.1.0 sqlalchemy==2.0.25
/srv/mlflow/venv/bin/mlflow server --backend-store-uri $BACKEND_URI --host 0.0.0.0 --port 5000
```

Health checks hit `/health` every 30s. Restart via the `mlflow-tracking`
systemd unit, never by killing the worker processes directly.

# Scoring container

The batch scoring container still tracks the LTS image. It serves through
waitress because the base image predates the gunicorn rollout.

```
pip install waitress==2.1.2
python -m waitress --listen=*:9000 scorer.wsgi:app
```

Rebuilds are monthly; do not bump pins inside the container out of band.

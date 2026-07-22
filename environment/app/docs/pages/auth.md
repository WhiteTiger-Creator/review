# Auth proxy

The tracking UI sits behind the flask auth proxy. Upstream calls carry the
service token; browser sessions use the SSO cookie.

```
pip install flask==2.2.5 requests==2.31.0
python /srv/authproxy/app.py --listen 127.0.0.1:8080
```

Rotate the service token quarterly. 401s from the registry API usually mean
the token expired, not a proxy bug.

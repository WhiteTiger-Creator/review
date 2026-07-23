# authgw

Internal authentication gateway for Meridian Logistics. Issues session
tokens on password login, supports a "remember me" cookie fallback, and
lets admins mint service tokens for internal integrations.

See [docs/API.md](docs/API.md) for the full endpoint reference.

## Development

```
make build   # compile ./bin/authgw
make test    # run the unit test suite
make run     # build and start the server on :8080
```

Configuration is read from the environment; see `internal/config`.

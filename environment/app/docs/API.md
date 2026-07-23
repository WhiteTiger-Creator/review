# authgw API reference

Internal authentication gateway. All request/response bodies are JSON
unless noted otherwise.

## POST /auth/register

Create a new account. New accounts always get `role: "user"`; there is no
self-service way to become an admin.

Request:

```json
{"username": "alice", "password": "at-least-8-chars"}
```

`username` must be at least 3 characters, `password` at least 8. On
success, returns `201` with `{"status": "created"}`. Returns `409` if the
username is already taken.

## POST /auth/login

Request:

```json
{"username": "alice", "password": "at-least-8-chars", "remember": false}
```

On success, returns `200` with:

```json
{"token": "<HS256 JWT>"}
```

If `remember` is `true`, the response also includes `"remember_token"`
and the response sets an `HttpOnly` `remember_token` cookie. Returns `401`
on bad credentials.

## GET /api/profile

Requires either an `Authorization: Bearer <token>` header or a valid
`remember_token` cookie. Returns `200` with:

```json
{"username": "alice", "role": "user"}
```

Returns `401` if the caller cannot be resolved.

## GET /admin/users

Same authentication as `/api/profile`, but the resolved caller must have
`role: "admin"`. Returns `200` with:

```json
{"users": [{"id": 1, "username": "admin", "role": "admin"}, ...]}
```

Returns `403` otherwise.

## POST /admin/service-tokens

Admin-only. Mints an RS256-signed service token for internal
integrations:

```json
{"service_token": "<RS256 JWT>"}
```

## GET /admin/audit-log

Admin-only. Returns the most recent 50 login attempts, newest first:

```json
{"entries": [{"ID": 12, "Event": "login_success", "Username": "alice", "CreatedAt": "2026-01-01 00:00:00"}, ...]}
```

## GET /.well-known/jwks.json

Public. Publishes the RSA public key used to sign service tokens, as a
standard JWK set:

```json
{"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": "authgw-service-key", "n": "...", "e": "..."}]}
```

## GET /healthz

Liveness probe. Always `200` with `{"status": "ok", "instance_id": "<per-replica id>"}`.

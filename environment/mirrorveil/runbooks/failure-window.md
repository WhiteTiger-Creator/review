# Probe, grace, and recovery

Service-ops standard for Mirrorveil edge health and stale delivery. Operators confirm process and backend state via probe results, `X-Edge-State`, `X-Origin-Node`, and `inspect-cache`.

## Backends

Named backends:

- `primary_origin` at `127.0.0.1:18191`
- `secondary_origin` at `127.0.0.1:18192`

New fetches use the first healthy backend, with primary preferred when it is healthy.

## Health probe

Both backends share one HTTP probe:

- `GET /__mirror_health HTTP/1.1`
- Host `health.mirrorveil.invalid`
- timeout `200ms`, interval `250ms`, window `4`, threshold `2`, initial `1`

The Nginx health resource returns `200` with body `ready` and no cookies or cacheable artifact metadata.

## Freshness windows

Eligible fixture objects:

- freshness: origin `max-age` of one second
- grace: five seconds
- keep: twenty seconds

These windows are uniform across public artifact fixtures.

## Outage delivery

A still-fresh cached object is served as `HIT` even when both origins are sick.

A stale object may be served as `GRACE` only when both origins are sick, freshness has expired, and the request is still inside the five-second grace window. If either origin is healthy, stale content is not used for a new request — fetch from the preferred healthy origin instead.

After grace expires with both origins still sick, or for an uncached URL while both are sick, the client receives `503 Service Unavailable` with `X-Edge-State: SYNTH` (not a bare backend error and not `PASS`).

## Recovery

When any origin becomes healthy again, new stale requests must not serve GRACE — refetch from a healthy origin instead (edge state must not be GRACE; status `200` from the preferred healthy origin). Once primary is healthy, that refetch returns to primary without a VCL reload or process restart. If only secondary is healthy, the refetch uses secondary. Recovery must not wipe unrelated cache state.

## Stack lifecycle

A stop/start cycle must leave no duplicate Varnish or Nginx processes, recreate runtime directories, leave the content-addressed `mv_<16 hex>` VCL generation active (not a temporary boot label such as `boot` or `boot_reload`), restore probes and primary preference, preserve origin content, and not treat stale PID files as authority. After start, `inspect-cache` must again report `preferred_backend=primary_origin` with both probes Healthy when both origins are up.

## inspect-cache contract

`/srv/mirrorveil/bin/inspect-cache` must print space-separated `key=value` tokens. Do not rename keys to shorter forms such as `varnish=` or `primary=`. With a healthy preferred-primary stack, output must include at least these exact keys:

```text
varnish_state=running
client_port=18091
management_port=18092
primary_state=running
secondary_state=running
primary_probe=Healthy
secondary_probe=Healthy
preferred_backend=primary_origin
```

Probe values use exactly `Healthy` or `Sick`. `preferred_backend` is `primary_origin` when primary is healthy, else `secondary_origin` when only secondary is healthy, else `none`.

## Operator tools

`/srv/mirrorveil/bin/cache-control` supports:

```text
cache-control origin-down primary|secondary
cache-control origin-up primary|secondary
```

`origin-down` stops the named Nginx origin and waits until health fails. `origin-up` starts it from the installed config and waits until health succeeds.

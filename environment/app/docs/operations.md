# Operations

## Commands

```text
signingd run --config /app/config/current.toml
signingd run --config /app/config/legacy.toml
signingd inspect --config /app/config/current.toml
```

## Behavior

- `run` processes available queue files and exits when the queue is drained.
- The service may replace workers according to `max_jobs_per_worker`.
- State under `/app/state` is durable and is inspected at startup.
- Logs are written under `/var/log/signing`.
- A nonzero exit indicates at least one configuration, job, token, or publication error.
- Completed jobs are not republished on a subsequent run.
- Operators may remove queue files only after observing a corresponding accepted output record.

## Inspect

`inspect` reports whether the active configuration can resolve each configured logical key against the token. It does not publish signing records.

## Startup recovery

At the start of `run`, reconcile durable state under `/app/state` and any existing files under `/output/signed` before accepting new work:

1. Finish publication for any valid staged records under `/app/state`.
2. Scan accepted finals under `/output/signed/jobs/` (including when the journal is empty and no staging entry exists) and rebuild `/output/signed/index.json` so every accepted final appears exactly once.
3. A valid final that is merely missing from the index must be restored into a consistent index. Do not require journal `published` evidence to accept that final, and do not treat missing index membership as a conflict.
4. When a queued job already has a matching accepted final, do not republish or re-sign it — but still ensure it is present in `index.json` after startup reconciliation.
5. Journal phases that end at `signed` without `published` are incomplete until publication finishes; do not treat `signed` alone as durable completion.

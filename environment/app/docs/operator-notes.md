# GraphRun pipeline operator notes

## Startup order

1. `/app/pkg/ops/build-offline.sh` — prepare `/app/pkg` and `/app/release-mirror` so `/app/release-mirror/build/libs/release-mirror.jar` exists. Honor `GRADLE_BIN` (default `/opt/gradle/bin/gradle`), `GRADLE_USER_HOME`, and `GRADLE_CACHE_TEMPLATE` when set (contract §12.1).
2. `/app/pkg/ops/start-release-mirror.sh` — loopback MLflow source mirror on `127.0.0.1:18081`.
3. `/app/pkg/ops/fetch-mlflow-release.sh` — fetch, verify, and extract the pinned MLflow tarball used for callback-schema validation.
4. `/app/pkg/ops/start-pkg.sh` — Spring Boot API on `127.0.0.1:18082`.
5. `/app/pkg/ops/generate-signing-manifest.sh <absolute-run-directory>` — pass an absolute fixture directory such as `/data/runs/visible-run-a` (not a bare `run_id`); drive callbacks and write digest/manifest artifacts under `/output` (or `GRAPHRUN_OUTPUT` when set). Requires `$MLFLOW_RELEASE_CACHE/schema.path` from step 3 (contract §8.2 / §12.2).

## Output directory

Default artifact directory is `/output/`. Set `GRAPHRUN_OUTPUT` to an absolute directory to redirect `run-attestation.json` and `signing-manifest.json`. `/app/pkg/ops/generate-signing-manifest.sh` and the GraphRun API must honor that override; writing only to a hardcoded `/output/` path breaks verifier reruns that inject `GRAPHRUN_OUTPUT`. When `GRAPHRUN_OUTPUT` is unset, both artifacts under `/output/` must still include a non-empty `policy_commit_id` — validating only under a temporary override directory is insufficient.

**Per-invocation, not startup-only:** the verifier may export a different absolute `GRAPHRUN_OUTPUT` on each `generate-signing-manifest.sh` call while the GraphRun service is already running. `start-pkg.sh` does not restart a healthy JVM, so a Spring property bound once at process start will still point at the earlier directory (often `/output/`). Read `GRAPHRUN_OUTPUT` on every script invocation (and/or on every artifact-write request) and ensure both artifacts land under that invocation’s directory. Contract §3.5 includes a local `graph_digest` reference vector for offline self-checks before relying on the verifier.

## Policy recovery

The working tree lacks `config/signing-policy.yaml` after INF-4412. Use the operations manual
(`/app/docs/graph-run-signer-operations-manual.md`) together with local Git reflogs and unreachable
objects to recover the single authorized `2026.1` policy commit. Built-in permissive fallbacks must
not be used for production artifact emission. After recovery, the authorized YAML must exist on disk at
`/app/pkg/config/signing-policy.yaml` (not only in memory).

## Graph digests and manifests

Canonicalization and digest rendering are specified in contract §3. Use the §3.5 worked field lists
and gold digests (`ref-g1` / `ref-g2` / `ref-g3` and `/data/runs/visible-run-a/graph.json` →
`2fd15541530fc3ac…`) as the local self-check vector before treating digests — or any driver helper
that rewrites fixture placeholders — as fixed; framing sketch in §3.6. A length-prefixed helper that
still diverges from the worked field lists is non-compliant even when it matches a still-broken
`GraphCanonicalizer`.

Digests are bare 64-char lowercase hex. `run-attestation.json` must be the flat §10.1 object at
the file root (not nested under `"attestation"`). `signing-manifest.json` must validate against
`/app/docs/signing-manifest.schema.json` with the flat required field set in contract §10.2 and
`additionalProperties: false`. Do not add `attestation_sha256`, `run_id`, `signature`, or other
extras — `signature` lives only in `run-attestation.json`. When `GRAPHRUN_OUTPUT` is unset, both
artifacts must land under `/output/` with a non-empty `policy_commit_id`. Keep key material and
raw callback bodies out of logs (contract §11.2). Default GraphRun API base URL / port follow
contract §9 and the §12 ops table (`SIGNER_URL` / `SIGNER_PORT`).

## Callback schema source

Validate callbacks only against the schema extracted from the verified MLflow release
(`$MLFLOW_RELEASE_CACHE/schema.path`). `/app/docs/bundled/run_callback.schema.json` is a stale
non-normative approximation — it omits `PENDING` and other contract fields — and must not be used
for intake validation (contract §6.1).

Read `schema.path` **lazily on every** callback validation and sign request. Do not resolve the
marker once in a Spring `@Bean` constructor/factory and reuse that path for the process lifetime,
and do not fall back to the bundled approximation when the marker is missing at JVM start. A warm
interactive session (fetch before `start-pkg.sh`) can mask a construction-time snapshot that
fails under a verifier cold start where the cache is cleared and the JVM may come up before or
without a pre-existing marker (contract §6.1).

## Service wiring

Repair the in-tree Java / Gradle / Spring Boot sources under `/app/pkg` — do not replace the
GraphRun API with a Python sidecar that needs undeclared deps (for example PyYAML) missing from
the verifier image (contract §12.1).

`PolicyLoader` takes **two** constructor arguments:

```java
new PolicyLoader(properties.policyPath(), properties.repoRoot())
```

A one-argument `new PolicyLoader(policyPath)` does not match the shipped type and will not
compile (contract §12.1).

## Release fetch

`/app/pkg/ops/fetch-mlflow-release.sh` must read `MLFLOW_RELEASE_URL` (default
`http://127.0.0.1:18081/releases/mlflow-2.16.2.tar.gz` — keep the `/releases/` path prefix and
tarball name; do not shorten to `http://127.0.0.1:18081`), `MLFLOW_RELEASE_SHA256_FILE`, and
`MLFLOW_RELEASE_CACHE` (defaults in contract §8), verify the pinned release digest on every use
including cache hits (a warm `schema.path` or `.verified-*` marker must not skip re-hash), and
**if verification fails exit non-zero without refetching or healing the cache** (contract §8.2).
Reject redirects outside the configured loopback mirror origin.

On success the script **must** write the absolute extracted schema path to
`$MLFLOW_RELEASE_CACHE/schema.path`. `/app/pkg/ops/generate-signing-manifest.sh` and the GraphRun
API read that marker for callback-schema location and `callback_schema_sha256` — this is the
normative inter-script handoff (contract §8.2). Do not invent a different marker filename.

Also document probe URLs `http://127.0.0.1:18081/redirect-external` and
`http://127.0.0.1:18082/v1/callbacks`, plus literal policy text `policy_version: 2026.1`.

## Callback identity and replay

- Synthetic/novel `run_id` values (for example `callback-replay-run`, `identity-run`) MUST be
  accepted on the first schema-valid `PENDING`/`RUNNING` callback even when no
  `/data/runs/<id>/` fixture exists and the run was never pre-registered on disk (contract §7.2).
  Do not HTTP **400** solely because a fixture file is missing.
- Visible fixture callbacks under `/data/runs/*/callbacks/` may use all-zero placeholder
  `graph_digest` values. Those placeholders are not normative — substitute the contract §3
  framed digest of the run’s `graph.json` (and `run_id` / `experiment_id` from `run.json`)
  before POST; see contract §7.2.
- First accepted callback for a `run_id` binds the presented `experiment_id` and `graph_digest`;
  later mismatches → HTTP **400**.
- First-time accept (including synthetic first `PENDING`) → HTTP **200** with JSON boolean
  `"accepted": true`. Do **not** return HTTP **202** for a newly accepted callback; contract §7.3
  uses **200** for both first-time accepts and exact replays.
- Same `event_id` with a different canonical callback body → HTTP **409** (conflict), not **400**.
- Exact same `event_id` + canonical body → idempotent HTTP **200** with JSON including boolean `"accepted": true` (not the string `"true"`, and not `{"status": "accepted"}` or `{"status": "replayed"}` as a stand-in; see contract §7.3).

## Handoff

When local self-checks pass — authorized policy on disk, offline jars built, `schema.path`
wired, synthetic first `PENDING` returns HTTP **200** (not **202**) with boolean `accepted`
true, exact-replay **200** / conflicting **409** match contract §7.3, and
`generate-signing-manifest.sh /data/runs/visible-run-a` wrote both artifacts under `/output`
(or the active `GRAPHRUN_OUTPUT`) — stop. Leave `/app/pkg` and `/output` for the grading
harness. Do not launch another full `build-offline.sh` / Gradle clean rebuild, keep probing
decoy helpers, or kill a healthy `start-pkg.sh` JVM after validation.

## Diagnostics

`/app/pkg/ops/reproduce-signing-failures.sh` prints a concise mismatch summary for equivalent-graph,
callback replay (expect **409** on conflicting replay), missing-policy, and release-cache scenarios.

Pinned release bytes: `/data/mlflow-release/mlflow-2.16.2.tar.gz`.
Fixture roots: `/data/runs/visible-run-a`, `/data/runs/visible-run-b` with
`/data/runs/visible-run-a/graph.json`, `/data/runs/visible-run-a/run.json`, and
`/data/runs/visible-run-b/graph.json`.
Health: `http://127.0.0.1:18081/health` and `http://127.0.0.1:18082/health`.
Callback intake: `http://127.0.0.1:18082/v1/callbacks`.
External redirect probe: `http://127.0.0.1:18081/redirect-external`.
Signer log: `/tmp/graphrun-signer/graph-run-signer.log`.
Verifier scratch: `TERMINUS_VERIFIER_ROOT` (default `/tmp/terminus-verifier`); redirect-probe caches may use a `redir-cache` directory name.
Literal policy text may include `policy_version: 2026.1`.
Attestation output includes a `signature` over contract-defined signing bytes; digests in the
manifest include the pinned release digest and schema digest.
Verifier helpers: Python `socket`, `urllib`, `hashlib`, `cryptography`, `decimal`,
`unicodedata`, `jsonschema`, and `verifier_support` (imported by `/tests/test_outputs.py`).
Offline Gradle knobs: `GRADLE_BIN`, `GRADLE_USER_HOME`, `GRADLE_CACHE_TEMPLATE` (contract §12.1).

## Incident references

See operations manual section **INF-4412** for the history rewrite that removed the active policy from
HEAD while preserving recoverable commits in reflogs.

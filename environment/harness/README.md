# mlflow-registry-harness

A small Maven (Java 17) harness that migrates an exported MLflow model-registry bundle
into an H2 metadata database by replaying Lua migrations, then exports the migrated tables
in a fixed canonical order so the result can be verified by SHA-256 digest.

## What it does

`MigrationRunner` drives the full pipeline:

1. **Unpack** `mlflow_registry_bundle.tar.gz` into `target/bundle` (`BundleUnpacker`).
   The bundle carries MLflow run exports, model signature JSON, and environment YAML for
   context; it does not carry the seed database or any checkpoint config.
2. **Load** the H2 seed database (`SeedDatabaseLoader`) into a fresh file-based H2 database
   under `target/`, rebuilt on every run so replays start from the same state.
3. **Replay** the Lua migrations in version order through an in-JVM
   [LuaJ](https://github.com/luaj/luaj) bridge (`LuaMigrationBridge`), then **replay the
   backfill migrations a second time against the same database**. See below.
4. **Export** the migrated tables to `target/registry_export.jsonl` in a fixed
   table/column/row order (`CanonicalExporter`) and compute its SHA-256 (`Sha256`).

Migrations are replayed from the loose on-disk `migrations/` directory (the source of
truth). Version order comes from the numeric prefix of each `VNNN_*.lua` file name.

### Double application

Schema migrations run once, the way a real migration tool applies them once per database.
Backfills (V003 and up) are applied **twice in a row against the same connection**, because
in production a backfill is re-run whenever upstream metadata changes. The second
application sees the first one's output, so a backfill that only works against virgin state
will not survive it. This is strictly stronger than requiring two whole harness runs to
agree.

### The bridge

Migrations reach the database and the Hub only through the globals the bridge installs:

- `db.query(sql)` → array of row tables keyed by lowercase column name
- `db.update(sql)` → affected row count
- `http.get(url)` → response body; **raises on any non-200**, with the status in the message
- `json.decode(text)` → Lua table
- `crypto.sha256(text)` → lowercase hex digest

The Lua environment is built by hand rather than via `JsePlatform.standardGlobals()`, so
`io.*`, `os.*`, `require`/`package.*`, `dofile`/`loadfile` and `luajava.*` are never
installed. `db.query`/`db.update` additionally reject SQL that reaches outside the database
(H2's `CSVREAD`/file-I/O functions, `CREATE ALIAS`/`CREATE TRIGGER` Java interop, linked
datasources).

### Hub access

`HubConfigClient` accepts only `https://huggingface.co/...` URLs. Two kinds are reachable:
the revision API (`/api/models/{repo}/revision/{tag}`), which resolves a tag to the commit
it points at, and file access at an exact commit
(`/{repo}/resolve/{commit}/{file}`). Responses come from the sealed data service, keyed by
exact URL, so the pipeline is byte-reproducible regardless of network state. The service
throttles some repos on first contact within a run, exactly as the real Hub does.

### Sealed data service

The seed SQL and the checkpoint fixtures are served by `/opt/_sealed/data_service.pyc`, a
compiled-only background process `SealedDataService.java` starts lazily and talks to over
loopback. "Sealed" means bytecode-only, not secret — everything it serves is an *input*,
and reading a checkpoint config is exactly what the migration does. What the task protects
is the correct *output*, and that is protected by the export digest, which reveals nothing.

## Specification

`spec/BACKFILL_CONTRACT.md` is normative. `spec/worked/` contains one full tensor-accounting
example and two additional checkpoint inputs for practicing generalization.

## Layout

```
pom.xml                         Maven build (H2, LuaJ, commons-compress, JUnit 5)
spec/
  BACKFILL_CONTRACT.md          normative specification for V003
  worked/                       one walkthrough and two additional checkpoint inputs
migrations/
  V001_add_hf_pin_columns.lua           schema: Hub pin columns
  V002_add_version_metadata_columns.lua schema: model_architecture + resolved commit
  V003_backfill_hf_model_metadata.lua   the backfill (incomplete -- this is the task)
mlflow_registry_bundle.tar.gz   input bundle (run exports, signatures, environment YAML)
src/main/java/com/example/registry/
  MigrationRunner.java    pipeline entry point
  BundleUnpacker.java     tar.gz extraction
  SeedDatabaseLoader.java H2 seed loader
  LuaMigrationBridge.java sandboxed LuaJ bridge (db/http/json/crypto helpers)
  HubConfigClient.java    Hugging Face Hub fetch
  SealedDataService.java  lazily starts/locates the sealed data service
  CanonicalExporter.java  deterministic JSONL export
  HarnessPaths.java       path resolution
  Sha256.java             digest helper
src/test/java/com/example/registry/
  MigrationHarnessTest.java  end-to-end checks; reports what is outstanding, not what it
                             should be
```

## Running

```sh
# Compile, run the JUnit suite, and produce target/registry_export.jsonl:
mvn -q -f pom.xml verify

# Produce the export without running the suite (useful while iterating):
mvn -q -f pom.xml package -Dmaven.test.skip=true
```

`verify` runs `MigrationRunner` during `prepare-package`, so `target/registry_export.jsonl`
is always written after a full build. A correct migration produces an export whose SHA-256
matches the digest recorded at image build time (`/opt/_sealed/registry_export.sha256`).

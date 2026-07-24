# mlflow-registry-harness

A small Maven (Java 17) harness that migrates an exported MLflow model-registry
bundle into an H2 metadata database by replaying Lua migrations, then exports the
migrated tables in a fixed canonical order so the result can be verified by
SHA-256 digest.

## What it does

`MigrationRunner` drives the full pipeline:

1. **Unpack** `mlflow_registry_bundle.tar.gz` into `target/bundle`
   (`BundleUnpacker`, backed by commons-compress). This bundle carries MLflow
   run exports, model signature JSON, and environment YAML for context; it does
   *not* carry the seed database contents or the Hugging Face config fixtures
   (see below).
2. **Load** the H2 seed database (`SeedDatabaseLoader`) into a fresh file-based
   H2 database under `target/`, rebuilt on every run so replays start from the
   same state. The seed DDL/INSERT script itself is fetched from the sealed
   data service, not read from a local file.
3. **Replay** the Lua migrations in version order through an in-JVM
   [LuaJ](https://github.com/luaj/luaj) bridge (`LuaMigrationBridge`). The bridge
   exposes DB query/update helpers and an HTTP GET helper to the migration
   scripts; there is no native `lua5.4` interpreter — Lua runs entirely inside
   the JVM via `org.luaj:luaj-jse`, and that JVM's Lua environment is built by
   hand (not `JsePlatform.standardGlobals()`) so `io`/`os`/`require`/`dofile`/
   `luajava` are never installed — migrations can only reach the database and
   the Hub through the globals this bridge installs. Hugging Face Hub configs
   are fetched through `HubConfigClient`, which only accepts
   `https://huggingface.co/...` URLs.
4. **Export** the migrated tables to `target/registry_export.jsonl` in a fixed
   table/column/row order (`CanonicalExporter`), and compute its SHA-256
   (`Sha256`).

Migrations are replayed from the loose on-disk `migrations/` directory (the
source of truth). Version order comes from the numeric prefix of each
`VNNN_*.lua` file name. `HarnessPaths` resolves all input/output locations.

### Sealed data service

The seed database's DDL/INSERT script and the pinned Hugging Face config
fixtures are not shipped as files anywhere in this image. They're baked into
`environment/sealed/data_service.py`, which is compiled to bytecode at image
build time and shipped as `/opt/_sealed/data_service.pyc` with no `.py` source
alongside it. `SealedDataService.java` lazily starts that process (if it isn't
already running) and talks to it over a `127.0.0.1`-only HTTP endpoint;
`SeedDatabaseLoader` and `HubConfigClient` are its only callers. There is
nothing on disk in this repo to `cat` your way to the seed lineage or the
config values — the pipeline still runs exactly the same either way.

## Layout

```
pom.xml                         Maven build (H2, LuaJ, commons-compress, JUnit 5)
migrations/
  V001_add_hf_pin_columns.lua           schema: add HF pin columns
  V002_add_version_metadata_columns.lua schema: add version metadata columns
  V003_backfill_hf_model_metadata.lua   backfill HF model metadata via the bridge
mlflow_registry_bundle.tar.gz   input bundle (run exports, signatures, environment YAML)
expected/registry_export.sha256 expected digest of a correct canonical export
src/main/java/com/example/registry/
  MigrationRunner.java   pipeline entry point
  BundleUnpacker.java    tar.gz extraction
  SeedDatabaseLoader.java H2 seed loader (fetches DDL/INSERTs from the sealed service)
  LuaMigrationBridge.java sandboxed LuaJ bridge (DB + HTTP helpers only)
  HubConfigClient.java   Hugging Face Hub config fetch (sealed service, live fallback)
  SealedDataService.java lazily starts/locates the sealed data service
  CanonicalExporter.java deterministic JSONL export
  HarnessPaths.java      path resolution
  Sha256.java            file digest helper
src/test/java/com/example/registry/
  MigrationHarnessTest.java  end-to-end pipeline + digest assertions
```

## Running

```sh
# Compile, run the JUnit suite, and produce target/registry_export.jsonl:
mvn -q -f pom.xml verify
```

`verify` runs `MigrationRunner` during `prepare-package`, so
`target/registry_export.jsonl` is always written after a full build. A correct
migration produces an export whose SHA-256 matches
`expected/registry_export.sha256`.

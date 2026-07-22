# Configuration

Effective dungeon configuration is assembled in this exact sequence:

1. **Select the configuration file:**
   - explicit `--config`;
   - otherwise non-empty `TRIVIA_CONFIG`;
   - otherwise `/app/config/dungeon.toml`.
2. **Initialize built-in defaults.**
3. **Parse the selected TOML file.**
4. **Apply non-empty `TRIVIA_*` environment variables.**
5. **Apply explicitly supplied CLI flags.**

Override precedence:

```text
CLI > non-empty environment > TOML > defaults
```

An empty environment value is treated as absent and does not override a TOML value.

## Precedence examples

| Setting | TOML | Environment | CLI | Effective |
|---------|------|-------------|-----|-----------|
| dataset | `/data/a.parquet` | `/data/b.parquet` | `/data/a.parquet` | `/data/a.parquet` |
| contracts | `/data/contracts` | (unset) | (unset) | `/data/contracts` |

## Environment variables

| Variable | CLI flag | Purpose |
|----------|----------|---------|
| `TRIVIA_ROOT` | `--root` | Application root directory |
| `TRIVIA_CONFIG` | `--config` | Dungeon TOML path |
| `TRIVIA_DATASET` | `--dataset` | Parquet dataset path |
| `TRIVIA_CONTRACTS` | `--contracts` | JSON Schema directory |
| `TRIVIA_STATE` | `--state` | Audit state file path |
| `TRIVIA_OUTPUT` | `--output` | Report output directory |

## Path rules

Relative `root`, `dataset`, `contracts`, `output`, and `state` values read from TOML resolve from the **TOML file's parent directory**. Absolute TOML paths remain absolute.

`content_dir` is different: after the final effective `root` is known, a relative `content_dir` resolves from that effective root.

Command-line and environment paths are used as supplied and normalized.

The process current working directory is **never** an authority for TOML-relative values. Changing CWD must not change reports or input identity.

Example:

```text
If /scratch/case/config/dungeon.toml declares root = "../.." and
content_dir = "bundle", the root resolves from the TOML directory and the final
content directory is <effective-root>/bundle.
```

## Defaults

| Field | Default |
|-------|---------|
| root | `/app` |
| dataset | `/data/trivia_qa_sample.parquet` |
| contracts | `/data/contracts` |
| output | `/output` |
| state | `/app/.state/audit-state.json` |

Audit and playthrough share the same default state path: `/app/.state/audit-state.json`.

## Verbose diagnostics

Pass `--verbose` to print effective values and their source layer (`default`, `toml`, `env`, `cli`).

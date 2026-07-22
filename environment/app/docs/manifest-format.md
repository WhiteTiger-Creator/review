# Manifest Format

Dungeon content is authored as YAML manifests and TOML configuration. Before JSON Schema validation, YAML is converted to a JSON-compatible tree.

## YAML scalar semantics

Manifests use **YAML 1.2 JSON-compatible scalar resolution**:

| Source token | Loaded JSON value |
| ------------ | ----------------- |
| `true`       | Boolean `true`    |
| `false`      | Boolean `false`   |
| `null`       | JSON null         |
| `on`         | String `"on"`     |
| `off`        | String `"off"`    |
| `yes`        | String `"yes"`    |
| `no`         | String `"no"`     |

The same string behavior applies regardless of letter case when the token is not a JSON boolean or JSON null token.

These values must remain strings when used as room IDs, aliases, titles, answers, or map values. Loading must not use YAML 1.1 implicit boolean coercion. Conversion to the JSON tree happens before JSON Schema validation. A room whose ID is `on` or `off` is valid when the schema otherwise permits it.

## Artifact kinds

| Kind | Location | Schema |
|------|----------|--------|
| Room | `bundle/chambers/*.yaml` | `room.schema.json` |
| Encounter | `bundle/nodes/*.yaml` | `encounter.schema.json` |
| Scoring | `bundle/weights/*.yaml` | `scoring.schema.json` |
| Dungeon config | `config/*.toml` | `dungeon-config.schema.json` |
| Answer script | `config/*answers*.toml` | `answers.schema.json` |

Each artifact declares a `version` field selecting the schema variant.

## Trivia locators

Encounters reference trivia records in the Parquet dataset using one of:

### Stable ID (preferred)

```yaml
trivia:
  question_id: "tc_12345"
```

Resolution queries the full dataset for the exact `question_id`:

- **Zero matching rows** produce:

  ```text
  pointer: /trivia/question_id
  code: dataset.missing-id
  ```

- **Exactly one matching row** resolves successfully.

- **More than one matching row** produces:

  ```text
  pointer: /trivia/question_id
  code: dataset.ambiguous-id
  ```

When the count is greater than one, do not select the first matching row. Do not add an ambiguous encounter to the valid registry. Continue validating other artifacts. Return audit exit code `2`.

SQL `LIMIT 1` or first-row selection does not satisfy the uniqueness contract.

### Legacy row + fingerprint

```yaml
trivia:
  row: 3
  question_sha256: "abc123..."
```

Legacy locator resolution:

1. `row` is **one-based**.
2. Dataset rows are ordered by `question_id ASC`.
3. Physical Parquet storage order is irrelevant.
4. Resolve the logical row first.
5. Compute the canonical fingerprint from that row's question text.
6. Compare the complete lowercase hexadecimal SHA-256 value.

Outcomes:

- An out-of-range row produces:

  ```text
  pointer: /trivia/row
  code: dataset.missing-id
  ```

- A row that exists but has a different fingerprint produces:

  ```text
  pointer: /trivia/question_sha256
  code: dataset.fingerprint-mismatch
  ```

- A fingerprint mismatch must not return the row as a valid resolved question.
- A stale fingerprint is a content violation and returns exit `2`.

## Question fingerprint

The canonical fingerprint of a question string is:

1. NFC Unicode normalization
2. Unicode case folding (`casefold`)
3. Remove characters that are not letters, digits, or whitespace (Unicode-aware)
4. Collapse whitespace and trim
5. SHA-256 hex digest of the UTF-8 bytes

Answer and alias matching uses the same normalization pipeline.

## Room aliases

Rooms may register aliases in `bundle/chambers/aliases.yaml`. Aliases are resolved whenever a room ID or edge target is looked up (start room, transitions, and encounter routing). Alias matching uses the same normalization as answer checking.

## Scoring

Scoring manifests define base points, difficulty multipliers, and streak bonuses. Streak thresholds are **inclusive** on the lower bound: a streak count equal to the threshold receives the bonus.

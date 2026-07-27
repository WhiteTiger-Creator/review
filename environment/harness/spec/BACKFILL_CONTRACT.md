# Backfill contract: resolved checkpoint architecture

Normative specification for `migrations/V003_backfill_hf_model_metadata.lua`.

Fixes conventions this migration must follow — field names, ordering, formatting,
tie-breaking. `spec/worked/` is authoritative wherever this contract leaves a convention
implicit.

## Scope

Backfill applies to a registered model if and only if **all** of:

- `registered_models.framework` is exactly `transformers`;
- `hf_repo_id` is not null;
- `hf_revision` is not null.

Every other row — other frameworks, unpinned models — must come out of the migration
**byte-identical to how it went in**, including any `hf_architecture_fingerprint` value
already present, even if stale. In-scope models' stale fingerprints must be replaced;
out-of-scope rows must be left exactly as they are, correct or not.

## Resolving a pin

`hf_revision` is a **tag**, not a commit. Two requests per model:

1. `GET https://huggingface.co/api/models/{repo_id}/revision/{tag}` → a JSON document whose
   `sha` field is the commit the tag currently points at. Record it in
   `registered_models.hf_resolved_commit`.
2. `GET https://huggingface.co/{repo_id}/resolve/{sha}/config.json` → the checkpoint config,
   fetched at the resolved **commit**, not the tag.

`http.get` raises on any non-200 response, with the status code in the message. A `429`
must be retried once.

## Field resolution

Every quantity below is looked up **top level first, then inside `text_config`**. A
top-level declaration always wins over a nested one, even when both are present.

A checkpoint is dual-tower only if it declares a `vision_config`; for such checkpoints,
every quantity refers to the language-model backbone (`text_config`), never the vision
tower. `text_config` alone, without `vision_config`, is not evidence of a vision tower and
resolves under the ordinary top-level-first rule.

## Columns

`model_architecture`, keyed by `fingerprint`:

| Column | Meaning |
| --- | --- |
| `fingerprint` | see below |
| `architecture` | first entry of `architectures`; if that list is empty or absent, `model_type` verbatim — not title-cased, not suffixed |
| `model_type` | `model_type`, verbatim |
| `hidden_size` | residual-stream width |
| `num_layers` | number of transformer blocks in the backbone: a single count, resolved under one field spelling, applied uniformly even when the checkpoint's real architecture divides work across more than one stack |
| `num_heads` | query heads |
| `num_kv_heads` | key/value heads. Absent ⇒ every query head has its own; a config declaring multi-query has exactly one |
| `head_dim` | explicit if declared, else derived; an explicit value that disagrees with `hidden_size / num_heads` is **correct as declared** — do not "fix" it |
| `ffn_dim` | feed-forward inner width. Absent ⇒ the `transformers` default of 4× the residual width |
| `attention_variant` | `mha`, `gqa`, or `mqa`, from the query:key-value head ratio |
| `total_param_count` | every weight and bias tensor the module instantiates |
| `active_param_count` | parameters engaged for a single token. Differs from total only for mixture-of-experts |
| `kv_cache_bytes_per_token` | bytes of key-value cache one token occupies across the whole backbone, at the checkpoint's declared `torch_dtype` |

`model_versions.hf_architecture_fingerprint` references `model_architecture.fingerprint`
for every version of an in-scope model.

### Counting parameters

Count every weight and bias tensor the module instantiates. Include normalization gains
(and biases where that normalization has them). Exclude anything that is a buffer rather
than a parameter.

`architectures` naming a task head (`ForSequenceClassification`, `ForTokenClassification`,
etc.) is not evidence about which tensors exist. Whether a vocabulary-sized output matrix
exists, and whether it is tied to the embedding matrix, is governed only by `vocab_size` and
`tie_word_embeddings` — see the worked examples' `lm_head` rows — regardless of what the
`architectures` name suggests the model is used for.

Which tensors exist, and how many of each, follows only from the quantities this contract
resolves and the rules it states here and in the worked examples — never from what a real
checkpoint's module class is separately known to instantiate or omit. A family-specific
detail outside those rules (an extra pooling or task head, a second stack accounted
separately from the first, a normalization scheme some real implementations share across
sub-layers) is not itself a reason to deviate from this contract's accounting. If a tensor
is not implied by a resolved quantity, it is not counted.

## Fingerprint

SHA-256, via `crypto.sha256`, over these twelve fields joined with `|`, in this order:

```
architecture|model_type|hidden_size|num_layers|num_heads|num_kv_heads|head_dim|ffn_dim|attention_variant|total_param_count|active_param_count|kv_cache_bytes_per_token
```

Whole numbers are written plainly, with no decimal point and no exponent, regardless of
how the config that produced them wrote the value. A field that could not be resolved
contributes the literal `null`. The digest is stored as the lowercase
hex `crypto.sha256` returns.

The fingerprint depends only on the resolved architecture — not the model name, the repo,
the commit, or the version. **Two models that resolve to the same architecture produce the
same fingerprint and must share a single `model_architecture` row.**

## Re-application

The harness applies this migration **twice against the same database**, back to back, and
requires the second application to change nothing. It creates no schema — `model_versions`,
`model_architecture` and `hf_resolved_commit` all already exist when it runs.

## Constraints

The database and the Hub are reachable only through `db.query` / `db.update` /
`http.get` / `json.decode` / `crypto.sha256`. There is no filesystem, no process, no socket
and no module loading in the migration's Lua environment. `db` rejects SQL that reaches
outside the database.

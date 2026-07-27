# Worked checkpoint 3 of 3 — absent vocabulary, defaulted feed-forward, MoE routing

Chosen because it exercises the cases where a quantity is *absent* rather than
differently spelled, and because it is the one place the routing conventions are shown.

## config.json — part A, an encoder with no vocabulary

```json
{
  "architectures": ["ElectraForPreTraining"],
  "model_type": "electra",
  "hidden_size": 768,
  "num_hidden_layers": 12,
  "num_attention_heads": 12,
  "hidden_act": "gelu",
  "max_position_embeddings": 512,
  "position_embedding_type": "absolute",
  "layer_norm_eps": 1e-12,
  "attention_bias": true,
  "mlp_bias": true,
  "torch_dtype": "float32"
}
```

### Resolved row

| Column | Value |
| --- | --- |
| `architecture` | `ElectraForPreTraining` |
| `model_type` | `electra` |
| `hidden_size` | 768 |
| `num_layers` | 12 |
| `num_heads` | 12 |
| `num_kv_heads` | 12 |
| `head_dim` | 64 |
| `ffn_dim` | 3072 |
| `attention_variant` | `mha` |

`ffn_dim` is **not** null. No feed-forward width is declared under any spelling, so the
library default applies: four times the residual width. A default the library would supply
is not a missing value.

No `vocab_size` appears anywhere, so `embed_tokens` and `lm_head` are both absent from the
inventory — and because the head does not exist, whether embeddings would be tied is moot.
`embed_positions` **is** present: positions are absolute and learned.

## config.json — part B, sparse routing

```json
{
  "architectures": ["MixtralForCausalLM"],
  "model_type": "mixtral",
  "hidden_size": 512,
  "num_hidden_layers": 4,
  "num_attention_heads": 8,
  "num_key_value_heads": 2,
  "intermediate_size": 1024,
  "num_local_experts": 4,
  "num_experts_per_tok": 2,
  "hidden_act": "silu",
  "rms_norm_eps": 1e-05,
  "vocab_size": 8192,
  "attention_bias": false,
  "mlp_bias": false,
  "tie_word_embeddings": false,
  "torch_dtype": "bfloat16"
}
```

### Additional tensors

Two things exist here that neither of the other worked checkpoints has:

- **experts.** The layer's feed-forward is replicated once per expert. `total_param_count`
  accounts for every expert the checkpoint instantiates; `active_param_count` accounts for
  the number a single token is routed through.
- **a routing network**, which maps the residual stream to a score per expert. Whether it
  is a parameter, and whether a single token traverses it, are questions about the
  architecture — answer them the same way you answered whether a rotary table is a
  parameter.

`active_param_count` equals `total_param_count` for any checkpoint that declares no
experts.

## What this example fixes

- An omitted feed-forward width takes the library's 4× default, and is not null.
- An absent vocabulary removes both the embedding matrix and the output head — and makes
  the tying question moot.
- Experts multiply the feed-forward tensors in `total` but not in `active`.

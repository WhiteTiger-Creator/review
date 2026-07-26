# Worked checkpoint 2 of 3 — grouped-query attention, gated MLP, RMSNorm, tied head

Chosen because it exercises the modern-decoder conventions and contrasts with worked
example 1 on every axis: grouped-query attention, a gated feed-forward, RMSNorm, rotary
positions, no biases, and tied embeddings.

## config.json

```json
{
  "architectures": ["Qwen2ForCausalLM"],
  "model_type": "qwen2",
  "hidden_size": 1536,
  "num_hidden_layers": 28,
  "num_attention_heads": 12,
  "num_key_value_heads": 2,
  "intermediate_size": 8960,
  "hidden_act": "silu",
  "max_position_embeddings": 32768,
  "rope_theta": 1000000.0,
  "rms_norm_eps": 1e-06,
  "vocab_size": 151936,
  "attention_bias": false,
  "mlp_bias": false,
  "tie_word_embeddings": true,
  "torch_dtype": "bfloat16"
}
```

## Resolved row

| Column | Value |
| --- | --- |
| `architecture` | `Qwen2ForCausalLM` |
| `model_type` | `qwen2` |
| `hidden_size` | 1536 |
| `num_layers` | 28 |
| `num_heads` | 12 |
| `num_kv_heads` | 2 |
| `head_dim` | 128 |
| `ffn_dim` | 8960 |
| `attention_variant` | `gqa` |

`head_dim` is not declared, so it is `1536 / 12`. Two key-value heads against twelve query
heads is grouped-query attention.

## What this checkpoint instantiates

The accounting takes the same form as worked example 1. What differs is which tensors
exist, and that follows from what this config declares:

- attention projections for queries, keys, values and output — but the key and value
  projections are not shaped like the query projection here, because there are two
  key-value heads against twelve query heads;
- no attention biases and no MLP biases: both are declared false;
- a feed-forward whose tensor count follows from `hidden_act`;
- two normalizations per layer and one after the last, of the kind `rms_norm_eps`
  implies — which does not carry the same tensors per normalization as worked example 1;
- a token embedding matrix;
- no learned position table: positions here are rotary;
- no separate output head: `tie_word_embeddings` is true.

Per-token key-value cache: one key and one value per layer, sized by the **key-value**
heads, at the stored width. Compare the result with worked example 1 — this model is far
larger and caches far less per token. That is what grouped-query attention is for.

## What this example fixes

Read against worked example 1, this checkpoint takes the opposite branch of every
conditional: gated versus plain feed-forward, RMSNorm versus LayerNorm, biases absent
versus present, rotary versus learned positions, tied versus untied head, and grouped-query
versus multi-head attention. Between the two, every conditional in the accounting has been
shown in both of its states.

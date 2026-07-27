# Worked checkpoint 1 of 3 — learned positions, non-gated MLP, biases, untied head

Chosen because it exercises every convention that adds parameters: absolute learned
position embeddings, a non-gated feed-forward, biases on both attention and MLP,
LayerNorm rather than RMSNorm, and an untied output head. None of these families appear
in the graded corpus; this is a specification example, not a preview.

## config.json

```json
{
  "architectures": ["OPTForCausalLM"],
  "model_type": "opt",
  "hidden_size": 1024,
  "num_hidden_layers": 12,
  "num_attention_heads": 16,
  "ffn_dim": 4096,
  "activation_function": "relu",
  "max_position_embeddings": 2048,
  "position_embedding_type": "absolute",
  "layer_norm_epsilon": 1e-05,
  "vocab_size": 50272,
  "attention_bias": true,
  "mlp_bias": true,
  "tie_word_embeddings": false,
  "torch_dtype": "float16"
}
```

## Resolved row

| Column | Value |
| --- | --- |
| `architecture` | `OPTForCausalLM` |
| `model_type` | `opt` |
| `hidden_size` | 1024 |
| `num_layers` | 12 |
| `num_heads` | 16 |
| `num_kv_heads` | 16 |
| `head_dim` | 64 |
| `ffn_dim` | 4096 |
| `attention_variant` | `mha` |

The remaining columns are counts, and they follow from the tensor inventory below rather
than from a table of answers. Work them out; the harness will tell you whether the export
as a whole is right.

## Tensor inventory

Every weight and bias tensor this checkpoint instantiates, with `H` = `hidden_size`,
`F` = `ffn_dim`, `L` = `num_layers`, `V` = `vocab_size`, `P` = `max_position_embeddings`,
`n_h` = `num_heads`, `n_kv` = `num_kv_heads`, `d_h` = `head_dim`.

| Tensor | Shape | Instantiated when |
| --- | --- | --- |
| `q_proj.weight` | `H × (n_h·d_h)` | always |
| `k_proj.weight` | `H × (n_kv·d_h)` | always |
| `v_proj.weight` | `H × (n_kv·d_h)` | always |
| `o_proj.weight` | `(n_h·d_h) × H` | always |
| `q_proj.bias` | `n_h·d_h` | `attention_bias` |
| `k_proj.bias`, `v_proj.bias` | `n_kv·d_h` each | `attention_bias` |
| `o_proj.bias` | `H` | `attention_bias` |
| `mlp.gate.weight` | `H × F` | gated activation only — **not here** |
| `mlp.up.weight` | `H × F` | always |
| `mlp.down.weight` | `F × H` | always |
| `mlp.up.bias` | `F` | `mlp_bias` |
| `mlp.down.bias` | `H` | `mlp_bias` |
| `input_norm.weight`, `post_attn_norm.weight` | `H` each | always, per layer |
| `input_norm.bias`, `post_attn_norm.bias` | `H` each | LayerNorm only (**here**); RMSNorm has no bias |
| `final_norm.*` | as above, once | after the last layer |
| `embed_tokens.weight` | `V × H` | `vocab_size` resolves |
| `embed_positions.weight` | `P × H` | `position_embedding_type` is `absolute` (**here**) |
| `lm_head.weight` | `V × H` | `vocab_size` resolves **and** embeddings are not tied (**here**) |

Rotary position tables and causal masks are buffers, not parameters, and never appear.

Per-token key-value cache: `2 · L · n_kv · d_h · bytes(torch_dtype)` — one key and one
value per layer, sized by the **key-value** heads, at the checkpoint's stored width.
`float16` is two bytes per element.

## What this example fixes

- A non-gated feed-forward instantiates **two** matrices, not three.
- LayerNorm carries a gain **and** a bias, so it contributes `2H` per normalization.
- Attention biases are sized by each projection's **output** width, which for K and V is
  the key-value width, not `H`.
- Learned absolute positions are parameters and are counted.
- An untied output head is a second `V × H` matrix.

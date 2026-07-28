# Additional checkpoint input

Derive the resolved row and parameter accounting from the contract.

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

# Additional checkpoint input

Derive the resolved row and parameter accounting from the contract.

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

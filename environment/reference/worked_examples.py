"""Authoring-time helper: computes the worked-example rows in spec/worked/ from the same
rules the reference V003 implements. Not shipped in the image; run by hand when the
worked examples change. Kept in environment/reference/ alongside the reference migration
so the two stay in sync.
"""

import hashlib
import json

DTYPE_BYTES = {
    "float32": 4, "fp32": 4, "float": 4,
    "float16": 2, "fp16": 2, "half": 2, "bfloat16": 2, "bf16": 2,
    "float64": 8, "fp64": 8, "double": 8,
    "int8": 1, "uint8": 1,
}


def resolve(cfg, *keys):
    """Top level first, then inside text_config. Numeric values are normalized to int:
    a config may legitimately write an integer-valued dimension in exponent notation
    (1.536e3), which JSON decodes to a float, and every quantity resolved here is a count
    or a width."""
    def coerce(v):
        if isinstance(v, bool) or not isinstance(v, float):
            return v
        return int(v) if v.is_integer() else v

    for k in keys:
        if cfg.get(k) is not None:
            return coerce(cfg[k])
    text = cfg.get("text_config")
    if isinstance(text, dict):
        for k in keys:
            if text.get(k) is not None:
                return coerce(text[k])
    return None


def normalize(cfg):
    archs = cfg.get("architectures")
    architecture = archs[0] if archs else cfg.get("model_type")

    hidden = resolve(cfg, "hidden_size", "dim", "n_embd", "d_model")
    layers = resolve(cfg, "num_hidden_layers", "n_layers", "n_layer", "num_layers")
    heads = resolve(cfg, "num_attention_heads", "n_heads", "n_head", "num_heads")

    if resolve(cfg, "multi_query") is True:
        kv_heads = 1
    else:
        kv_heads = resolve(cfg, "num_key_value_heads") or heads

    head_dim = resolve(cfg, "head_dim")
    if head_dim is None and hidden is not None and heads is not None:
        head_dim = hidden // heads

    ffn = resolve(cfg, "intermediate_size", "d_ff", "n_inner", "ffn_dim", "hidden_dim")
    if ffn is None and hidden is not None:
        ffn = 4 * hidden

    if kv_heads == heads:
        variant = "mha"
    elif kv_heads == 1:
        variant = "mqa"
    else:
        variant = "gqa"

    act = resolve(cfg, "hidden_act", "activation", "activation_function") or ""
    gated = act == "silu" or "glu" in act

    is_rms = resolve(cfg, "rms_norm_eps") is not None
    norm_size = hidden if is_rms else 2 * hidden

    attn_bias = resolve(cfg, "attention_bias") is True
    mlp_bias = resolve(cfg, "mlp_bias") is True

    proj = heads * head_dim
    kv_proj = kv_heads * head_dim
    attn = hidden * proj + 2 * hidden * kv_proj + proj * hidden
    if attn_bias:
        attn += proj + 2 * kv_proj + hidden

    if gated:
        mlp_one = 3 * hidden * ffn + (2 * ffn + hidden if mlp_bias else 0)
    else:
        mlp_one = 2 * hidden * ffn + (ffn + hidden if mlp_bias else 0)

    experts = resolve(cfg, "num_local_experts", "num_experts")
    top_k = resolve(cfg, "num_experts_per_tok")
    if experts is not None:
        router = hidden * experts
        mlp_total = experts * mlp_one + router
        mlp_active = top_k * mlp_one + router
    else:
        mlp_total = mlp_active = mlp_one

    per_layer_norms = 2 * norm_size
    backbone_total = layers * (attn + mlp_total + per_layer_norms) + norm_size
    backbone_active = layers * (attn + mlp_active + per_layer_norms) + norm_size

    vocab = resolve(cfg, "vocab_size")
    pos_type = resolve(cfg, "position_embedding_type")
    max_pos = resolve(cfg, "max_position_embeddings", "n_positions")
    embeddings = 0
    if vocab is not None:
        embeddings += vocab * hidden
    if pos_type == "absolute" and max_pos is not None:
        embeddings += max_pos * hidden

    tied = resolve(cfg, "tie_word_embeddings") is True
    head_params = 0 if (vocab is None or tied) else vocab * hidden

    total = backbone_total + embeddings + head_params
    active = backbone_active + embeddings + head_params

    dtype = resolve(cfg, "torch_dtype") or "float32"
    kv_cache = 2 * layers * kv_heads * head_dim * DTYPE_BYTES.get(dtype, 4)

    def f(v):
        # Mirrors the Lua reference's string.format("%d", ...): a whole-valued number
        # renders with no decimal point regardless of whether the config literal that
        # produced it was written as an integer or in exponent notation.
        if v is None:
            return "null"
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return str(v)
        return str(int(v))

    parts = [f(architecture), f(cfg.get("model_type")), f(hidden), f(layers), f(heads),
             f(kv_heads), f(head_dim), f(ffn), f(variant), f(total), f(active), f(kv_cache)]
    fingerprint = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    return {
        "fingerprint": fingerprint,
        "architecture": architecture,
        "model_type": cfg.get("model_type"),
        "hidden_size": hidden,
        "num_layers": layers,
        "num_heads": heads,
        "num_kv_heads": kv_heads,
        "head_dim": head_dim,
        "ffn_dim": ffn,
        "attention_variant": variant,
        "total_param_count": total,
        "active_param_count": active,
        "kv_cache_bytes_per_token": kv_cache,
    }, "|".join(parts)


WORKED = {
    "opt-style": {
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
        "attention_bias": True,
        "mlp_bias": True,
        "tie_word_embeddings": False,
        "torch_dtype": "float16",
    },
    "qwen2-style": {
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
        "attention_bias": False,
        "mlp_bias": False,
        "tie_word_embeddings": True,
        "torch_dtype": "bfloat16",
    },
    "electra-style": {
        "architectures": ["ElectraForPreTraining"],
        "model_type": "electra",
        "hidden_size": 768,
        "num_hidden_layers": 12,
        "num_attention_heads": 12,
        "hidden_act": "gelu",
        "max_position_embeddings": 512,
        "position_embedding_type": "absolute",
        "layer_norm_eps": 1e-12,
        "attention_bias": True,
        "mlp_bias": True,
        "torch_dtype": "float32",
    },
}


if __name__ == "__main__":
    for name, cfg in WORKED.items():
        row, fp_input = normalize(cfg)
        print("=" * 78)
        print(name)
        print("-- config.json --")
        print(json.dumps(cfg, indent=2))
        print("-- fingerprint input --")
        print(fp_input)
        print("-- row --")
        print(json.dumps(row, indent=2))

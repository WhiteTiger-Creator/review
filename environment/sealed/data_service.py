"""Sealed data service (compiled to .pyc; this .py source is never shipped in the final
image). Serves the seed SQL and the pinned Hugging Face Hub fixtures -- both the tag ->
commit-sha revision documents and the config.json documents -- over a localhost-only HTTP
endpoint, and records which URLs a harness run actually fetched.

Design note: this service deliberately does NOT hide its inputs. Everything it serves is
readable by anything in the container, which is fine -- reading a checkpoint config is
exactly what the migration under test is supposed to do. What must never be recoverable is
the *correct output*, and that is protected by the fact that the only complete oracle is a
SHA-256 digest (non-invertible), plus a battery of behavioural perturbation checks that
need no ground truth at all. There is therefore no secret at rest anywhere in this file,
and the /control endpoints below are intentionally unauthenticated: knowing that a
perturbation is coming does not help anyone pass it, because the only way to satisfy it is
to genuinely read the config and compute from it.

Callers: SealedDataService (process launch), SeedDatabaseLoader (/seed), HubConfigClient
(/hf), MigrationRunner (/control/run-begin).
"""

from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_HOST = "127.0.0.1"
_PORT = 8743

DEFAULT_SEED = "hub-pin-backfill-2026-07-default"

_LOCK = threading.Lock()


# --------------------------------------------------------------------------------------
# Number rendering.
#
# Two checkpoints in this corpus write some of their integer-valued dimensions in
# exponent notation (1.536e3 rather than 1536). This is legal JSON for the same number and
# it happens in the wild -- configs that have been round-tripped through a serializer that
# renders every number as a float come out this way.
#
# It matters here because the Lua bridge's JSON reader (see JsonParser.parseNumber in
# LuaMigrationBridge.java) only yields a Lua integer when the literal token contains no
# '.', 'e' or 'E'; otherwise it yields a double. The arithmetic is identical either way --
# every value involved is far below 2^53 -- but Lua's default number-to-string conversion
# renders a whole-valued double as "1536.0", and the architecture fingerprint is a hash of
# rendered text. So a migration that lets Lua choose the rendering produces the right
# numbers and the wrong digest, on two checkpoints out of nineteen, with nothing in the
# exported integer columns looking wrong.
#
# The contract already requires whole numbers to be written plainly with no decimal point.
# This makes that requirement load-bearing instead of theoretical.
# --------------------------------------------------------------------------------------

class _RawNumber:
    """Carries a numeric value plus the exact JSON literal it must be serialized as, so a
    config can present a number in exponent notation without the serializer normalizing
    it. Rendered via _dump_config below, which substitutes the literal back in."""

    __slots__ = ("literal", "value")

    def __init__(self, value, literal):
        self.value = value
        self.literal = literal


def _exp_notation(value):
    """Render an integer as an equivalent exponent-notation literal: 1536 -> 1.536e3."""
    text = str(int(value))
    digits = text.rstrip("0")
    trailing_zeros = len(text) - len(digits)
    if len(digits) == 1:
        return _RawNumber(value, f"{digits}e{trailing_zeros}")
    mantissa = digits[0] + "." + digits[1:]
    return _RawNumber(value, f"{mantissa}e{trailing_zeros + len(digits) - 1}")


def _dump_config(config):
    """json.dumps, but _RawNumber values are emitted as their exact literal."""
    placeholders = {}

    def encode(obj):
        if isinstance(obj, _RawNumber):
            key = f"@@raw{len(placeholders)}@@"
            placeholders[key] = obj.literal
            return key
        if isinstance(obj, dict):
            return {k: encode(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [encode(v) for v in obj]
        return obj

    text = json.dumps(encode(config))
    for key, literal in placeholders.items():
        text = text.replace(f'"{key}"', literal)
    return text


# --------------------------------------------------------------------------------------
# Deterministic, version-stable pseudo-randomness. hashlib rather than `random` so a given
# seed produces the identical corpus on every CPython build.
# --------------------------------------------------------------------------------------

def _h(seed, key):
    return int.from_bytes(hashlib.sha256((seed + "|" + key).encode("utf-8")).digest()[:8], "big")


def _pick(seed, key, options):
    return options[_h(seed, key) % len(options)]


def _commit_sha(seed, repo, tag):
    return hashlib.sha256((seed + "|commit|" + repo + "|" + tag).encode("utf-8")).hexdigest()[:40]


def _stale_fp(name):
    """A plausible-looking but wrong fingerprint left behind by a half-finished earlier
    backfill attempt. 64 hex chars so it fits the column and looks legitimate."""
    return hashlib.sha256(("stale-backfill-v1|" + name).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------
# Checkpoint dimension generation.
# --------------------------------------------------------------------------------------

def _round_to(value, multiple):
    return int(multiple * max(1, round(value / float(multiple))))


def _dims(seed, key, gated):
    num_heads = _pick(seed, key + "/nh", [8, 12, 16, 20, 24, 32])
    head_dim = 64
    hidden = num_heads * head_dim
    layers = _pick(seed, key + "/L", [6, 8, 10, 12, 16, 20, 24, 28, 32])
    # Vocabularies are kept modest so that every derived parameter count stays comfortably
    # inside 32-bit range. The task is about resolving and counting correctly, not about
    # how a particular Lua runtime renders a large integer; keeping the arithmetic small
    # removes that as a confound.
    vocab = _pick(seed, key + "/V", [16000, 24576, 30000, 32000, 40960])
    positions = _pick(seed, key + "/P", [512, 1024, 2048])
    if gated:
        ffn = _round_to(hidden * 8.0 / 3.0, 128)
    else:
        ffn = 4 * hidden
    kv_candidates = [d for d in (num_heads // 8, num_heads // 4, num_heads // 2)
                     if d >= 1 and num_heads % d == 0]
    num_kv = kv_candidates[_h(seed, key + "/kv") % len(kv_candidates)]
    return {
        "hidden": hidden,
        "heads": num_heads,
        "head_dim": head_dim,
        "layers": layers,
        "vocab": vocab,
        "positions": positions,
        "ffn": ffn,
        "kv": num_kv,
    }


# --------------------------------------------------------------------------------------
# Config templates, one per checkpoint family. Each returns an ordered dict that is
# serialized to the config.json body the migration fetches.
# --------------------------------------------------------------------------------------

def _cfg_llama(seed, key, arch, tied, dtype, model_type="llama"):
    d = _dims(seed, key, gated=True)
    cfg = {}
    if arch is not None:
        cfg["architectures"] = arch
    cfg["model_type"] = model_type
    cfg["hidden_size"] = d["hidden"]
    cfg["num_hidden_layers"] = d["layers"]
    cfg["num_attention_heads"] = d["heads"]
    cfg["num_key_value_heads"] = d["kv"]
    cfg["intermediate_size"] = d["ffn"]
    cfg["hidden_act"] = "silu"
    cfg["max_position_embeddings"] = 8192
    cfg["rope_theta"] = 10000.0
    cfg["rms_norm_eps"] = 1e-05
    cfg["vocab_size"] = d["vocab"]
    cfg["attention_bias"] = False
    cfg["mlp_bias"] = False
    cfg["tie_word_embeddings"] = tied
    cfg["torch_dtype"] = dtype
    return cfg


def _cfg_gpt2(seed, key, arch):
    d = _dims(seed, key, gated=False)
    # This checkpoint's config has been round-tripped through a serializer that rendered
    # every number as a float, so its dimensions arrive in exponent notation. Same values,
    # different literals. See the _RawNumber note at the top of this file.
    return {
        "architectures": arch,
        "model_type": "gpt2",
        "n_embd": _exp_notation(d["hidden"]),
        "n_layer": _exp_notation(d["layers"]),
        "n_head": _exp_notation(d["heads"]),
        "n_inner": _exp_notation(d["ffn"]),
        "n_positions": _exp_notation(d["positions"]),
        "activation_function": "gelu_new",
        "position_embedding_type": "absolute",
        "layer_norm_epsilon": 1e-05,
        "vocab_size": _exp_notation(d["vocab"]),
        "attention_bias": True,
        "mlp_bias": True,
        "torch_dtype": "float32",
    }


def _cfg_bert(seed, key, arch):
    d = _dims(seed, key, gated=False)
    return {
        "architectures": arch,
        "model_type": "bert",
        "hidden_size": d["hidden"],
        "num_hidden_layers": d["layers"],
        "num_attention_heads": d["heads"],
        "intermediate_size": d["ffn"],
        "hidden_act": "gelu",
        "max_position_embeddings": d["positions"],
        "position_embedding_type": "absolute",
        "layer_norm_eps": 1e-12,
        "vocab_size": d["vocab"],
        "attention_bias": True,
        "mlp_bias": True,
        "torch_dtype": "float32",
    }


def _cfg_distilbert(seed, key, arch):
    d = _dims(seed, key, gated=False)
    return {
        "architectures": arch,
        "model_type": "distilbert",
        "dim": d["hidden"],
        "n_layers": d["layers"],
        "n_heads": d["heads"],
        "hidden_dim": d["ffn"],
        "activation": "gelu",
        "max_position_embeddings": d["positions"],
        "position_embedding_type": "absolute",
        "layer_norm_eps": 1e-12,
        "vocab_size": d["vocab"],
        "attention_bias": True,
        "mlp_bias": True,
        "torch_dtype": "float32",
    }


def _cfg_dmodel(seed, key, arch, model_type):
    """d_model / num_layers / num_heads / d_ff naming, modern internals (RoPE + RMSNorm +
    gated MLP). Exercises the T5-family key spellings without dragging in relative
    attention bias parameters."""
    d = _dims(seed, key, gated=True)
    return {
        "architectures": arch,
        "model_type": model_type,
        "d_model": d["hidden"],
        "num_layers": d["layers"],
        "num_heads": d["heads"],
        "num_key_value_heads": d["kv"],
        "d_ff": d["ffn"],
        "hidden_act": "geglu",
        "num_decoder_layers": max(2, d["layers"] // 2),
        "rope_theta": 10000.0,
        "rms_norm_eps": 1e-06,
        "vocab_size": d["vocab"],
        "attention_bias": False,
        "mlp_bias": False,
        "tie_word_embeddings": False,
        "torch_dtype": "bfloat16",
    }


def _cfg_falcon(seed, key, arch):
    """Multi-query attention declared via `multi_query`, explicit head_dim, LayerNorm with
    rotary positions (so 'RoPE implies RMSNorm' is not a safe shortcut)."""
    d = _dims(seed, key, gated=False)
    return {
        "architectures": arch,
        "model_type": "falcon",
        "hidden_size": d["hidden"],
        "num_hidden_layers": d["layers"],
        "num_attention_heads": d["heads"],
        "head_dim": d["head_dim"],
        "multi_query": True,
        "ffn_dim": d["ffn"],
        "hidden_act": "gelu",
        "rope_theta": 10000.0,
        "layer_norm_epsilon": 1e-05,
        "vocab_size": d["vocab"],
        "attention_bias": False,
        "mlp_bias": False,
        "tie_word_embeddings": True,
        "torch_dtype": "bfloat16",
    }


def _cfg_gemma(seed, key, arch):
    """head_dim is explicit and deliberately does NOT equal hidden_size / num_heads, the
    way Gemma-7B and Llama-3.2 configs behave. num_heads * head_dim is the projection
    width; hidden_size stays the residual-stream width."""
    layers = _pick(seed, key + "/L", [18, 24, 28])
    vocab = _pick(seed, key + "/V", [32000, 49152])
    return {
        "architectures": arch,
        "model_type": "gemma",
        "hidden_size": 1536,
        "num_hidden_layers": layers,
        "num_attention_heads": 16,
        "num_key_value_heads": 16,
        "head_dim": 128,
        "intermediate_size": 8192,
        "hidden_act": "geglu",
        "max_position_embeddings": 8192,
        "rope_theta": 10000.0,
        "rms_norm_eps": 1e-06,
        "vocab_size": vocab,
        "attention_bias": False,
        "mlp_bias": False,
        "tie_word_embeddings": True,
        "torch_dtype": "bfloat16",
    }


def _cfg_moe(seed, key, arch):
    # Deliberately narrow and shallow: the total parameter count multiplies by the expert
    # count, and the verifier perturbs that upward, so the checkpoint is sized to leave
    # plenty of headroom under those perturbations.
    d = _dims(seed, key, gated=True)
    hidden = 768
    ffn = 2048
    experts = _pick(seed, key + "/E", [3, 4])
    top_k = _pick(seed, key + "/K", [1, 2])
    return {
        "architectures": arch,
        "model_type": "mixtral",
        "hidden_size": hidden,
        "num_hidden_layers": _pick(seed, key + "/L", [6, 8]),
        "num_attention_heads": 12,
        "num_key_value_heads": _pick(seed, key + "/kv", [2, 4]),
        "intermediate_size": ffn,
        "num_local_experts": experts,
        "num_experts_per_tok": top_k,
        "hidden_act": "silu",
        "max_position_embeddings": 32768,
        "rope_theta": 1000000.0,
        "rms_norm_eps": 1e-05,
        "vocab_size": d["vocab"],
        "attention_bias": False,
        "mlp_bias": False,
        "tie_word_embeddings": False,
        "torch_dtype": "bfloat16",
    }


def _cfg_vlm(seed, key, arch):
    """Dual-tower: the language-model backbone lives in text_config, and a vision tower
    sits alongside it. Nothing about the backbone is declared at the top level. The
    backbone's dimensions also arrive in exponent notation (see the _RawNumber note)."""
    text = _cfg_llama(seed, key + "/text", None, False, "bfloat16", model_type="llama")
    text.pop("architectures", None)
    for field in ("hidden_size", "num_hidden_layers", "num_attention_heads",
                  "num_key_value_heads", "intermediate_size", "vocab_size"):
        if field in text:
            text[field] = _exp_notation(text[field])
    vision = {
        "model_type": "vit",
        "hidden_size": 1024,
        "num_hidden_layers": 24,
        "num_attention_heads": 16,
        "intermediate_size": 4096,
        "image_size": 224,
        "patch_size": 14,
    }
    return {
        "architectures": arch,
        "model_type": "vision-encoder-decoder",
        "is_encoder_decoder": True,
        "text_config": text,
        "vision_config": vision,
    }


def _cfg_precedence(seed, key, arch):
    """Declares backbone quantities at BOTH the top level and inside text_config, with
    different values. The top-level declaration is the authoritative one."""
    inner = _cfg_llama(seed, key + "/inner", None, False, "bfloat16")
    inner.pop("architectures", None)
    outer_dims = _dims(seed, key + "/outer", gated=True)
    return {
        "architectures": arch,
        "model_type": "ocr-encoder-decoder",
        "hidden_size": outer_dims["hidden"],
        "num_hidden_layers": outer_dims["layers"],
        "num_attention_heads": outer_dims["heads"],
        "num_key_value_heads": outer_dims["kv"],
        "intermediate_size": outer_dims["ffn"],
        "hidden_act": "silu",
        "rope_theta": 10000.0,
        "rms_norm_eps": 1e-05,
        "vocab_size": outer_dims["vocab"],
        "attention_bias": False,
        "mlp_bias": False,
        "tie_word_embeddings": False,
        "torch_dtype": "bfloat16",
        "text_config": inner,
    }


def _cfg_novocab(seed, key):
    """Audio/vision encoder: no vocabulary anywhere, and an empty architectures list."""
    d = _dims(seed, key, gated=False)
    return {
        "architectures": [],
        "model_type": "wav2vec2",
        "hidden_size": d["hidden"],
        "num_hidden_layers": d["layers"],
        "num_attention_heads": d["heads"],
        "intermediate_size": d["ffn"],
        "hidden_act": "gelu",
        "layer_norm_eps": 1e-05,
        "position_embedding_type": "rotary",
        "attention_bias": True,
        "mlp_bias": True,
        "torch_dtype": "float32",
    }


# --------------------------------------------------------------------------------------
# The registry itself.
#
# Columns: name, created_time, description, framework, repo, tag, family, dim key,
# architectures value, versions. `dim key` is what the generator seeds dimensions on, so
# two checkpoints sharing a key resolve to the identical architecture (used for the dedup
# pair and the tied/untied twin pair).
#
# versions entries: (version, source_run_id, parent_version, stage, stale_fingerprint)
# --------------------------------------------------------------------------------------

_MODELS = [
    ("qa-encoder", 1700000000, "Extractive QA sentence encoder", "transformers",
     "acme/qa-encoder-base", "v1.2.0", "bert", "K01", ["BertModel"],
     [(1, "run-qa-0001", None, "Archived", None),
      (2, "run-qa-0002", 1, "Production", "qa-encoder")]),

    ("sentiment-classifier", 1700000100, "Binary sentiment classifier", "transformers",
     "acme/sentiment-distil", "v3.0.1", "distilbert", "K02",
     ["DistilBertForSequenceClassification"],
     [(1, "run-sent-0001", None, "Production", None)]),

    ("summarizer", 1700000200, "Abstractive summarizer", "transformers",
     "acme/summarizer-pegasus", "v2.5.0", "dmodel", "K03",
     ["PegasusXForConditionalGeneration"],
     [(1, "run-sum-0001", None, "Archived", "summarizer"),
      (2, "run-sum-0002", 1, "Staging", None),
      (3, "run-sum-0003", 2, "Production", None)]),

    ("code-generator", 1700000300, "Code generation transformer", "transformers",
     "acme/code-gpt", "v0.9.4", "gpt2", "K04", ["GPT2LMHeadModel"],
     [(1, "run-code-0001", None, "Staging", None),
      (2, "run-code-0002", 1, "Production", None)]),

    ("vision-captioner", 1700000400, "Vision-language caption generator", "transformers",
     "acme/vl-caption", "v1.0.0", "vlm", "K05", ["VisionEncoderDecoderModel"],
     [(1, "run-vl-0001", None, "Production", None)]),

    ("translator", 1700000500, "Encoder-decoder translation model", "transformers",
     "acme/translator-t5x", "v1.1.0", "dmodel", "K06", ["T5ForConditionalGeneration"],
     [(1, "run-tr-0001", None, "Archived", None),
      (2, "run-tr-0002", 1, "Production", "translator")]),

    ("embedding-retriever", 1700000600, "Dense passage retrieval embedding model",
     "transformers", "acme/embed-mistral", "v0.4.2", "llama", "SHARED", ["MistralModel"],
     [(1, "run-embed-0001", None, "Production", None)]),

    ("audio-classifier", 1700000700, "Audio event classification model", "transformers",
     "acme/audio-wav2vec", "v2.0.0", "novocab", "K08", None,
     [(1, "run-audio-0001", None, "Archived", None),
      (2, "run-audio-0002", 1, "Staging", None),
      (3, "run-audio-0003", 2, "Production", "audio-classifier")]),

    ("reranker", 1700000800, "Cross-encoder reranking model", "transformers",
     "acme/rerank-falcon", "v1.0.0", "falcon", "K09",
     ["FalconForSequenceClassification"],
     [(1, "run-rerank-0001", None, "Archived", None),
      (2, "run-rerank-0002", 1, "Production", None)]),

    ("anomaly-detector", 1700000900, "Time-series anomaly detection model", "transformers",
     None, None, None, None, None,
     [(1, "run-anomaly-0001", None, "Production", None)]),

    ("chat-assistant", 1700001000, "Mixture-of-experts chat model", "transformers",
     "acme/chat-moe", "v0.2.0", "moe", "K11", ["MixtralForCausalLM"],
     [(1, "run-chat-0001", None, "Staging", None),
      (2, "run-chat-0002", 1, "Production", "chat-assistant")]),

    ("doc-classifier", 1700001100, "Long document classifier (untied head)", "transformers",
     "acme/doc-untied", "v1.0.0", "llama_untied", "TWIN",
     ["LlamaForSequenceClassification"],
     [(1, "run-doc-0001", None, "Production", None)]),

    ("doc-classifier-lite", 1700001200, "Long document classifier (tied head)",
     "transformers", "acme/doc-tied", "v1.0.0", "llama_tied", "TWIN",
     ["LlamaForSequenceClassification"],
     [(1, "run-docl-0001", None, "Production", None)]),

    ("instruct-tuned", 1700001300, "Instruction-tuned variant of the retrieval backbone",
     "transformers", "acme/instruct-mistral", "v3.1.0", "llama", "SHARED", ["MistralModel"],
     [(1, "run-inst-0001", None, "Staging", None),
      (2, "run-inst-0002", 1, "Production", None)]),

    ("gemma-scorer", 1700001400, "Relevance scorer with decoupled head dimension",
     "transformers", "acme/gemma-scorer", "v1.4.0", "gemma", "K15",
     ["GemmaForSequenceClassification"],
     [(1, "run-gem-0001", None, "Production", None)]),

    ("legacy-forecaster", 1700001500, "Seasonal ARIMA demand forecaster", "statsmodels",
     "acme/legacy-arima", "v0.1.0", "bert", "K16", ["BertModel"],
     [(1, "run-leg-0001", None, "Production", "legacy-forecaster")]),

    ("speech-tagger", 1700001600, "State-space speech tagger", "ssm",
     "acme/mamba-tagger", "v0.3.0", "bert", "K17", ["BertModel"],
     [(1, "run-sp-0001", None, "Archived", "speech-tagger-v1"),
      (2, "run-sp-0002", 1, "Production", "speech-tagger-v2")]),

    ("ocr-reader", 1700001700, "Document OCR reader", "transformers",
     "acme/ocr-precedence", "v2.2.0", "precedence", "K18",
     ["OcrEncoderDecoderModel"],
     [(1, "run-ocr-0001", None, "Production", None)]),

    ("entity-linker", 1700001800, "Entity linking tagger", "transformers",
     "acme/entity-dangelo", "v1.0.0", "llama", "K19",
     ["D'AngeloForTokenClassification"],
     [(1, "run-ent-0001", None, "Production", None)]),

    ("long-context", 1700001900, "Long-context base model", "transformers",
     "acme/long-ctx", "v4.0.0", "llama_fp32_noarch", "K20", None,
     [(1, "run-long-0001", None, "Archived", None),
      (2, "run-long-0002", 1, "Production", None)]),
]

# Repos whose revision endpoint returns 429 on the first request of each harness run and
# 200 on retry. Exercises the retry path without introducing nondeterminism.
_FLAKY_REPOS = {"acme/summarizer-pegasus", "acme/chat-moe", "acme/entity-dangelo"}


def _build_config(seed, family, key, arch):
    if family == "bert":
        return _cfg_bert(seed, key, arch)
    if family == "gpt2":
        return _cfg_gpt2(seed, key, arch)
    if family == "distilbert":
        return _cfg_distilbert(seed, key, arch)
    if family == "dmodel":
        model_type = "t5" if "T5" in (arch[0] if arch else "") else "pegasus_x"
        return _cfg_dmodel(seed, key, arch, model_type)
    if family == "falcon":
        return _cfg_falcon(seed, key, arch)
    if family == "gemma":
        return _cfg_gemma(seed, key, arch)
    if family == "moe":
        return _cfg_moe(seed, key, arch)
    if family == "vlm":
        return _cfg_vlm(seed, key, arch)
    if family == "precedence":
        return _cfg_precedence(seed, key, arch)
    if family == "novocab":
        return _cfg_novocab(seed, key)
    if family == "llama":
        return _cfg_llama(seed, key, arch, False, "bfloat16")
    if family == "llama_untied":
        return _cfg_llama(seed, key, arch, False, "bfloat16")
    if family == "llama_tied":
        return _cfg_llama(seed, key, arch, True, "bfloat16")
    if family == "llama_fp32_noarch":
        cfg = _cfg_llama(seed, key, None, False, "float32")
        cfg["vocab_size"] = 262144
        return cfg
    raise ValueError("unknown family: " + str(family))


def _sql_str(value):
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _build_seed_sql(models):
    lines = [
        "-- MLflow model-registry seed database.",
        "-- Captured mid-migration: an earlier backfill attempt populated",
        "-- model_versions.hf_architecture_fingerprint for a handful of rows and was then",
        "-- abandoned. Those values are stale and, for models in scope, wrong.",
        "",
        "CREATE TABLE registered_models (",
        "    name          VARCHAR(128) PRIMARY KEY,",
        "    created_time  BIGINT       NOT NULL,",
        "    description   VARCHAR(512),",
        "    framework     VARCHAR(32)  NOT NULL",
        ");",
        "",
        "CREATE TABLE model_versions (",
        "    model_name                  VARCHAR(128) NOT NULL,",
        "    version                     INT          NOT NULL,",
        "    source_run_id               VARCHAR(64)  NOT NULL,",
        "    parent_version              INT,",
        "    current_stage               VARCHAR(32)  NOT NULL,",
        "    hf_architecture_fingerprint VARCHAR(64),",
        "    PRIMARY KEY (model_name, version),",
        "    FOREIGN KEY (model_name) REFERENCES registered_models(name)",
        ");",
        "",
    ]
    rows = []
    for (name, created, desc, framework, _repo, _tag, _fam, _key, _arch, _vs) in models:
        rows.append(
            f"    ({_sql_str(name)}, {created}, {_sql_str(desc)}, {_sql_str(framework)})")
    lines.append(
        "INSERT INTO registered_models (name, created_time, description, framework) VALUES")
    lines.append(",\n".join(rows) + ";")
    lines.append("")

    vrows = []
    for (name, _c, _d, _f, _repo, _tag, _fam, _key, _arch, versions) in models:
        for (version, run_id, parent, stage, stale) in versions:
            parent_sql = "NULL" if parent is None else str(parent)
            stale_sql = "NULL" if stale is None else _sql_str(_stale_fp(stale))
            vrows.append(
                f"    ({_sql_str(name)}, {version}, {_sql_str(run_id)}, {parent_sql}, "
                f"{_sql_str(stage)}, {stale_sql})")
    lines.append("INSERT INTO model_versions (model_name, version, source_run_id, "
                 "parent_version, current_stage, hf_architecture_fingerprint) VALUES")
    lines.append(",\n".join(vrows) + ";")
    lines.append("")
    return "\n".join(lines)


def _build(seed):
    """Materialize the whole corpus for a seed: seed SQL plus every URL the harness can
    fetch. Config documents are held as dicts (so overrides can be applied structurally,
    and so _RawNumber literals survive) and serialized per request; revision documents are
    plain JSON text."""
    documents = {}
    configs = {}
    for (name, _c, _d, _f, repo, tag, family, key, arch, _vs) in _MODELS:
        if repo is None:
            continue
        sha = _commit_sha(seed, repo, tag)
        rev_url = "https://huggingface.co/api/models/" + repo + "/revision/" + tag
        documents[rev_url] = json.dumps(
            {"_id": hashlib.sha256(repo.encode("utf-8")).hexdigest()[:24],
             "id": repo, "sha": sha, "tag": tag})
        cfg_url = "https://huggingface.co/" + repo + "/resolve/" + sha + "/config.json"
        configs[cfg_url] = _build_config(seed, family, key, arch)
    return {"seed_sql": _build_seed_sql(_MODELS), "documents": documents,
            "configs": configs}


# --------------------------------------------------------------------------------------
# Mutable service state.
# --------------------------------------------------------------------------------------

_state = {
    "seed": DEFAULT_SEED,
    "corpus": _build(DEFAULT_SEED),
    "fetched": set(),
    "overrides": {},   # repo -> {dotted.field: value}; None value deletes the field
    "rate_limited": set(),
}


def _apply_overrides(repo, cfg):
    """Structural copy of a config with any active perturbations applied. Copied by hand
    rather than through a JSON round-trip so _RawNumber literals survive."""

    def clone(obj):
        if isinstance(obj, dict):
            return {k: clone(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clone(v) for v in obj]
        return obj

    patch = _state["overrides"].get(repo)
    if not patch:
        return cfg
    out = clone(cfg)
    for dotted, value in patch.items():
        parts = dotted.split(".")
        node = out
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        if value is None:
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = value
    return out


def _repo_for_url(url):
    marker = "/api/models/"
    if marker in url:
        rest = url.split(marker, 1)[1]
        return rest.split("/revision/", 1)[0]
    rest = url.split("https://huggingface.co/", 1)[-1]
    return "/".join(rest.split("/")[:2])


def _document_for(url):
    corpus = _state["corpus"]
    if url.endswith("/config.json"):
        config = corpus["configs"].get(url)
        if config is None:
            return None
        return _dump_config(_apply_overrides(_repo_for_url(url), config))
    return corpus["documents"].get(url)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, status, body, content_type="text/plain; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/health":
            self._send(200, "ok")
            return

        if path == "/seed":
            self._send(200, _state["corpus"]["seed_sql"])
            return

        if path == "/fetched-urls":
            with _LOCK:
                self._send(200, json.dumps(sorted(_state["fetched"])), "application/json")
            return

        if path == "/control/run-begin":
            # Called by MigrationRunner at the start of every pipeline run: clears the
            # per-run fetch log and re-arms the one-shot rate limiter.
            with _LOCK:
                _state["fetched"] = set()
                _state["rate_limited"] = set()
            self._send(200, "ok")
            return

        if path == "/control/clear":
            with _LOCK:
                _state["overrides"] = {}
            self._send(200, "ok")
            return

        if path == "/control/perturb":
            repo = (query.get("repo") or [None])[0]
            field = (query.get("field") or [None])[0]
            raw = (query.get("value") or [None])[0]
            if not repo or not field:
                self._send(400, "repo and field are required")
                return
            value = None if raw is None else json.loads(raw)
            with _LOCK:
                _state["overrides"].setdefault(repo, {})[field] = value
            self._send(200, "ok")
            return

        if path == "/control/reseed":
            new_seed = (query.get("seed") or [DEFAULT_SEED])[0]
            with _LOCK:
                _state["seed"] = new_seed
                _state["corpus"] = _build(new_seed)
                _state["overrides"] = {}
                _state["fetched"] = set()
                _state["rate_limited"] = set()
            self._send(200, "ok")
            return

        if path == "/control/pinned":
            # Inventory of what is pinned for the current corpus. Inputs only -- never
            # resolved/expected values.
            inventory = []
            for (name, _c, _d, framework, repo, tag, _fam, _k, _a, _vs) in _MODELS:
                if repo is None:
                    continue
                sha = _commit_sha(_state["seed"], repo, tag)
                inventory.append({
                    "model": name, "framework": framework, "repo": repo, "tag": tag,
                    "sha": sha,
                    "revision_url": "https://huggingface.co/api/models/" + repo
                                    + "/revision/" + tag,
                    "config_url": "https://huggingface.co/" + repo + "/resolve/" + sha
                                  + "/config.json",
                })
            self._send(200, json.dumps(inventory), "application/json")
            return

        if path == "/hf":
            url = (query.get("url") or [None])[0]
            if url is None:
                self._send(400, "url is required")
                return
            repo = _repo_for_url(url)
            if "/revision/" in url and repo in _FLAKY_REPOS:
                with _LOCK:
                    first = repo not in _state["rate_limited"]
                    _state["rate_limited"].add(repo)
                if first:
                    self._send(429, "rate limited; retry")
                    return
            body = _document_for(url)
            if body is None:
                self._send(404, "not pinned")
                return
            with _LOCK:
                _state["fetched"].add(url)
            self._send(200, body, "application/json")
            return

        self._send(404, "not found")


def main():
    server = ThreadingHTTPServer((_HOST, _PORT), _Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()

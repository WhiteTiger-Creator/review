-- V003: resolve each registered model's pinned Hugging Face checkpoint and backfill its
-- architecture into model_architecture, pointing that model's version rows at it.
--
-- Scope is framework = 'transformers' with a non-null pin. Everything else -- other
-- frameworks, unpinned models -- is left exactly as seeded, including stale fingerprints
-- from the abandoned earlier backfill: rewriting rows outside this migration's remit is a
-- defect even when the rewrite would be an improvement.
--
-- Pins are tags, not commits, so each model costs two Hub requests: the revision API
-- resolves the tag to a commit, and config.json is then fetched at that commit. The Hub
-- throttles some repos on first contact, hence the retry.
--
-- Every quantity resolves top level first, then inside text_config, so a dual-tower
-- checkpoint's backbone is found while a top-level declaration still wins over a nested
-- one. The vision tower is never consulted.
--
-- Idempotency: the harness applies this twice against the same database. Every write is a
-- plain assignment or a MERGE keyed on the fingerprint, so the second application is a
-- no-op on the data.

local function sql_str(value)
  if value == nil then return "NULL" end
  return "'" .. tostring(value):gsub("'", "''") .. "'"
end

local function sql_int(value)
  if value == nil then return "NULL" end
  return string.format("%d", value)
end

-- Whole numbers are formatted explicitly rather than left to tostring, which would render
-- a numerically-whole float as "150.0" and change the digest.
local function fp_field(value)
  if value == nil then return "null" end
  if type(value) == "number" then return string.format("%d", value) end
  return tostring(value)
end

local function resolve(config, ...)
  local keys = {...}
  for _, key in ipairs(keys) do
    if config[key] ~= nil then return config[key] end
  end
  local text = config.text_config
  if text ~= nil then
    for _, key in ipairs(keys) do
      if text[key] ~= nil then return text[key] end
    end
  end
  return nil
end

local DTYPE_BYTES = {
  float32 = 4, fp32 = 4, float = 4,
  float16 = 2, fp16 = 2, half = 2, bfloat16 = 2, bf16 = 2,
  float64 = 8, fp64 = 8, double = 8,
  int8 = 1, uint8 = 1,
}

-- http.get raises on any non-200. A 429 is the Hub asking us to slow down, and succeeds on
-- retry; anything else is a real failure and propagates.
local function get_with_retry(url)
  local ok, body = pcall(http.get, url)
  if ok then return body end
  if tostring(body):find("429") then
    local ok2, body2 = pcall(http.get, url)
    if ok2 then return body2 end
    error(body2)
  end
  error(body)
end

local function normalize(config)
  local architectures = config.architectures
  local architecture
  if architectures ~= nil and architectures[1] ~= nil then
    architecture = architectures[1]
  else
    -- Empty or absent list: model_type verbatim, not title-cased or suffixed.
    architecture = config.model_type
  end

  local hidden = resolve(config, "hidden_size", "dim", "n_embd", "d_model")
  local layers = resolve(config, "num_hidden_layers", "n_layers", "n_layer", "num_layers")
  local heads = resolve(config, "num_attention_heads", "n_heads", "n_head", "num_heads")

  -- Key-value heads: multi-query declares one shared head; otherwise an explicit count, or
  -- one per query head when nothing is declared.
  local kv_heads
  if resolve(config, "multi_query") == true then
    kv_heads = 1
  else
    kv_heads = resolve(config, "num_key_value_heads") or heads
  end

  -- An explicit head_dim is authoritative even when it disagrees with hidden / heads: the
  -- projection width and the residual width are independently chosen in several families.
  local head_dim = resolve(config, "head_dim")
  if head_dim == nil and hidden ~= nil and heads ~= nil then
    head_dim = hidden / heads
  end

  -- An omitted feed-forward width is the library's 4x default, not an unresolved value.
  local ffn = resolve(config, "intermediate_size", "d_ff", "n_inner", "ffn_dim", "hidden_dim")
  if ffn == nil and hidden ~= nil then
    ffn = 4 * hidden
  end

  local variant
  if heads ~= nil and kv_heads ~= nil then
    if kv_heads == heads then variant = "mha"
    elseif kv_heads == 1 then variant = "mqa"
    else variant = "gqa" end
  end

  -- A gated MLP has three matrices (gate, up, down); a plain one has two.
  local act = resolve(config, "hidden_act", "activation", "activation_function") or ""
  local gated = (act == "silu") or (act:find("glu") ~= nil)

  -- RMSNorm is a gain only; LayerNorm carries a bias too.
  local is_rms = resolve(config, "rms_norm_eps") ~= nil
  local norm_size = is_rms and hidden or (2 * hidden)

  local attn_bias = resolve(config, "attention_bias") == true
  local mlp_bias = resolve(config, "mlp_bias") == true

  -- Q and O span the full projection width; K and V are sized by the key-value heads,
  -- which is the whole point of grouped-query attention.
  local proj = heads * head_dim
  local kv_proj = kv_heads * head_dim
  local attn = hidden * proj + 2 * hidden * kv_proj + proj * hidden
  if attn_bias then
    attn = attn + proj + 2 * kv_proj + hidden
  end

  local mlp_one
  if gated then
    mlp_one = 3 * hidden * ffn
    if mlp_bias then mlp_one = mlp_one + 2 * ffn + hidden end
  else
    mlp_one = 2 * hidden * ffn
    if mlp_bias then mlp_one = mlp_one + ffn + hidden end
  end

  -- Mixture of experts: total holds every expert plus the router; active holds only the
  -- experts a single token is routed to.
  local experts = resolve(config, "num_local_experts", "num_experts")
  local top_k = resolve(config, "num_experts_per_tok")
  local mlp_total, mlp_active
  if experts ~= nil then
    local router = hidden * experts
    mlp_total = experts * mlp_one + router
    mlp_active = top_k * mlp_one + router
  else
    mlp_total = mlp_one
    mlp_active = mlp_one
  end

  local per_layer_norms = 2 * norm_size
  local backbone_total = layers * (attn + mlp_total + per_layer_norms) + norm_size
  local backbone_active = layers * (attn + mlp_active + per_layer_norms) + norm_size

  -- Learned absolute positions are parameters; rotary tables are buffers and are not.
  local vocab = resolve(config, "vocab_size")
  local pos_type = resolve(config, "position_embedding_type")
  local max_pos = resolve(config, "max_position_embeddings", "n_positions")
  local embeddings = 0
  if vocab ~= nil then embeddings = embeddings + vocab * hidden end
  if pos_type == "absolute" and max_pos ~= nil then
    embeddings = embeddings + max_pos * hidden
  end

  -- A tied head reuses the embedding matrix and adds nothing.
  local tied = resolve(config, "tie_word_embeddings") == true
  local head_params = 0
  if vocab ~= nil and not tied then head_params = vocab * hidden end

  local total = backbone_total + embeddings + head_params
  local active = backbone_active + embeddings + head_params

  -- One key and one value per layer, sized by the key-value heads, at the stored width.
  local dtype = resolve(config, "torch_dtype") or "float32"
  local bytes = DTYPE_BYTES[dtype] or 4
  local kv_cache = 2 * layers * kv_heads * head_dim * bytes

  local model_type = config.model_type
  local parts = {
    fp_field(architecture), fp_field(model_type), fp_field(hidden), fp_field(layers),
    fp_field(heads), fp_field(kv_heads), fp_field(head_dim), fp_field(ffn),
    fp_field(variant), fp_field(total), fp_field(active), fp_field(kv_cache),
  }

  return {
    fingerprint = crypto.sha256(table.concat(parts, "|")),
    architecture = architecture,
    model_type = model_type,
    hidden_size = hidden,
    num_layers = layers,
    num_heads = heads,
    num_kv_heads = kv_heads,
    head_dim = head_dim,
    ffn_dim = ffn,
    attention_variant = variant,
    total_param_count = total,
    active_param_count = active,
    kv_cache_bytes_per_token = kv_cache,
  }
end

local models = db.query([[
  SELECT name, hf_repo_id, hf_revision
    FROM registered_models
   WHERE framework = 'transformers'
     AND hf_repo_id IS NOT NULL
     AND hf_revision IS NOT NULL
   ORDER BY name
]])

for _, model in ipairs(models) do
  local rev_url = "https://huggingface.co/api/models/" .. model.hf_repo_id
      .. "/revision/" .. model.hf_revision
  local commit = json.decode(get_with_retry(rev_url)).sha

  local cfg_url = "https://huggingface.co/" .. model.hf_repo_id
      .. "/resolve/" .. commit .. "/config.json"
  local meta = normalize(json.decode(get_with_retry(cfg_url)))

  db.update(
    "UPDATE registered_models SET hf_resolved_commit = " .. sql_str(commit) ..
    " WHERE name = " .. sql_str(model.name))

  -- MERGE, not INSERT: two models can resolve to the same architecture, and this migration
  -- is applied twice against the same database.
  db.update(
    "MERGE INTO model_architecture KEY(fingerprint) VALUES (" ..
    sql_str(meta.fingerprint) .. ", " ..
    sql_str(meta.architecture) .. ", " ..
    sql_str(meta.model_type) .. ", " ..
    sql_int(meta.hidden_size) .. ", " ..
    sql_int(meta.num_layers) .. ", " ..
    sql_int(meta.num_heads) .. ", " ..
    sql_int(meta.num_kv_heads) .. ", " ..
    sql_int(meta.head_dim) .. ", " ..
    sql_int(meta.ffn_dim) .. ", " ..
    sql_str(meta.attention_variant) .. ", " ..
    sql_int(meta.total_param_count) .. ", " ..
    sql_int(meta.active_param_count) .. ", " ..
    sql_int(meta.kv_cache_bytes_per_token) .. ")")

  db.update(
    "UPDATE model_versions SET hf_architecture_fingerprint = " ..
    sql_str(meta.fingerprint) ..
    " WHERE model_name = " .. sql_str(model.name))
end

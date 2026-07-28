-- V003: resolve each registered model's pinned Hugging Face checkpoint and backfill its
-- architecture into model_architecture, pointing that model's version rows at it.
--
-- STATUS: UNFINISHED, AND WRONG. This is where the previous attempt was abandoned. It
-- does not currently get through a single model -- the first fetch fails outright.
--
-- It was written against BERT-shaped checkpoints and never revisited. Since then the
-- registry has picked up checkpoints from families that name things differently, that
-- bury the language-model backbone one level down, that share key-value heads across
-- query heads, that gate their feed-forward, that route tokens to a subset of experts,
-- and that tie their output head to the embedding matrix. None of that is handled here.
-- The nil-guards below were added in a hurry to stop it erroring out partway; they make
-- it complete, not correct -- columns come out null that should have values, and values
-- come out that are wrong.
--
-- Getting it to run again is the first problem, not the last one.
--
-- See spec/BACKFILL_CONTRACT.md for what this migration is required to produce, and
-- spec/worked/ for examples of the accounting inputs.

local function sql_str(value)
  if value == nil then return "NULL" end
  return "'" .. tostring(value) .. "'"
end

local function sql_int(value)
  if value == nil then return "NULL" end
  return tostring(value)
end

local models = db.query([[
  SELECT name, hf_repo_id, hf_revision
    FROM registered_models
   ORDER BY name
]])

for _, model in ipairs(models) do
  if model.hf_repo_id ~= nil then
    local cfg_url = "https://huggingface.co/" .. model.hf_repo_id
        .. "/resolve/" .. model.hf_revision .. "/config.json"
    local config = json.decode(http.get(cfg_url))

    local architecture = "unknown"
    if config.architectures ~= nil and config.architectures[1] ~= nil then
      architecture = config.architectures[1]
    end

    local hidden = config.hidden_size
    local layers = config.num_hidden_layers
    local heads = config.num_attention_heads
    local ffn = config.intermediate_size
    local vocab = config.vocab_size

    local head_dim
    if hidden ~= nil and heads ~= nil then
      head_dim = hidden / heads
    end

    -- Attention is four square projections, the MLP is two hidden x ffn matrices, plus
    -- the token embeddings.
    local total
    if hidden ~= nil and layers ~= nil and ffn ~= nil and vocab ~= nil then
      total = layers * (4 * hidden * hidden + 2 * hidden * ffn) + vocab * hidden
    end

    local kv_cache
    if layers ~= nil and heads ~= nil and head_dim ~= nil then
      kv_cache = 2 * layers * heads * head_dim * 4
    end

    local fingerprint = crypto.sha256(
      architecture .. "|" .. tostring(config.model_type) .. "|"
      .. tostring(hidden) .. "|" .. tostring(layers))

    db.update(
      "MERGE INTO model_architecture KEY(fingerprint) VALUES (" ..
      sql_str(fingerprint) .. ", " ..
      sql_str(architecture) .. ", " ..
      sql_str(config.model_type) .. ", " ..
      sql_int(hidden) .. ", " ..
      sql_int(layers) .. ", " ..
      sql_int(heads) .. ", " ..
      sql_int(heads) .. ", " ..
      sql_int(head_dim) .. ", " ..
      sql_int(ffn) .. ", " ..
      "'mha', " ..
      sql_int(total) .. ", " ..
      sql_int(total) .. ", " ..
      sql_int(kv_cache) .. ")")

    db.update(
      "UPDATE model_versions SET hf_architecture_fingerprint = " .. sql_str(fingerprint))
  end
end

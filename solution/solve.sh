#!/bin/bash
# Reference solution for the MLflow registry Hugging Face metadata backfill task.
#
# Implements the unfinished part of migrations/V003_backfill_hf_model_metadata.lua so
# the harness produces the canonical export whose SHA-256 matches
# expected/registry_export.sha256. It derives all metadata from the registry rows +
# fetched Hub configs through the provided db/http helpers; nothing is hardcoded to the
# fixture.
#
# What the implementation has to get right, given what the shipped stub already sets up
# (querying registered_models; sql_quote/sql_number for building UPDATE statements):
#   1. Lineage        — never touch source_run_id/parent_version on any version; those
#                        columns belong to the run that actually produced that version,
#                        not to this backfill.
#   2. Idempotency     — only UPDATE existing version rows in place; never INSERT new
#                        version rows, so re-applying this migration is a no-op the
#                        second time.
#   3. Normalization   — the registered models span several Hugging Face model families,
#                        and their config.json files don't share one schema (GPT-2:
#                        n_embd/n_layer/n_head; DistilBERT: dim/n_layers/n_heads; T5:
#                        d_model/num_layers/num_heads; encoder-decoder checkpoints nest
#                        the real values under text_config; some configs omit
#                        architectures entirely, or include it as an empty list). Each
#                        field has to be resolved across those spellings, falling back
#                        into text_config, while not confusing decoy fields that sit
#                        alongside the real ones (T5's num_decoder_layers is not
#                        num_layers; Mistral's num_key_value_heads is not
#                        num_attention_heads).
#   4. Derivation      — one config (Falcon-style) gives no num-heads field at all under
#                        any spelling, only head_dim. Standard multi-head attention
#                        divides hidden_size evenly across heads, so hf_num_heads has to
#                        be derived as hidden_size / head_dim, not just looked up.
#   5. Unpinned models — not every registered model has hf_repo_id/hf_revision set; a
#                        model can be registered without ever having been pinned to a
#                        Hub checkpoint. Concatenating a nil hf_repo_id/hf_revision into
#                        a URL string errors out the whole migration (every model, not
#                        just the unpinned one), so unpinned models must be skipped.
set -euo pipefail

# Locate the harness root (the directory containing pom.xml).
dir="${PWD}"
if [ ! -f "${dir}/pom.xml" ]; then
  if [ -f /app/pom.xml ]; then
    dir=/app
  else
    while [ "${dir}" != "/" ] && [ ! -f "${dir}/pom.xml" ]; do
      dir="$(dirname "${dir}")"
    done
  fi
fi

target="${dir}/migrations/V003_backfill_hf_model_metadata.lua"

cat > "${target}" <<'LUA'
-- V003: backfill normalized Hugging Face Hub config metadata onto each registered
-- model's versions.
--
-- For every registered model we fetch its pinned Hub config via the HTTP helper and pull
-- the architecture / model type / hidden size / layer count / head count out of it,
-- tolerating the alternative key spellings used by different model families (BERT/BART,
-- GPT-2, DistilBERT, T5) and the nested text_config block that encoder-decoder
-- checkpoints use. Decoy fields that sit alongside the real ones (T5's
-- num_decoder_layers, GQA's num_key_value_heads) are deliberately not in the alias
-- lists below. When no head-count field is present under any spelling (Falcon-style
-- configs give only head_dim), the head count is derived from hidden_size / head_dim,
-- since standard multi-head attention divides hidden_size evenly across heads. The
-- values are written onto that model's own version rows.
--
-- This migration is a pure metadata backfill: it never touches version lineage
-- (source_run_id / parent_version) and every column is a plain assignment (not a
-- COALESCE-guarded accumulation), so re-applying it is idempotent.

local function sql_quote(value)
  if value == nil then
    return "NULL"
  end
  return "'" .. tostring(value):gsub("'", "''") .. "'"
end

local function sql_number(value)
  if value == nil then
    return "NULL"
  end
  return tostring(value)
end

-- Resolve a field across the alternative spellings used by BERT/DistilBERT/GPT2/T5, then
-- the nested text_config block that encoder-decoder checkpoints use. `keys[1]` is always
-- the canonical/BERT-style name, which is also what nested text_config blocks use.
local function resolve(config, keys)
  for _, key in ipairs(keys) do
    local value = config[key]
    if value ~= nil then
      return value
    end
  end
  local text_config = config.text_config
  if text_config ~= nil then
    return text_config[keys[1]]
  end
  return nil
end

local function normalize(config)
  local architecture
  if config.architectures ~= nil then
    architecture = config.architectures[1]
  end
  if architecture == nil then
    architecture = config.model_type
  end

  local hidden_size = resolve(config, {"hidden_size", "dim", "n_embd", "d_model"})
  local num_heads = resolve(config, {"num_attention_heads", "n_heads", "n_head", "num_heads"})
  if num_heads == nil and config.head_dim ~= nil and hidden_size ~= nil then
    -- No head-count field under any spelling; derive it the way standard multi-head
    -- attention relates these quantities: hidden_size = num_heads * head_dim.
    num_heads = hidden_size / config.head_dim
  end

  return {
    architecture = architecture,
    model_type = config.model_type,
    hidden_size = hidden_size,
    num_layers = resolve(config, {"num_hidden_layers", "n_layers", "n_layer", "num_layers"}),
    num_heads = num_heads,
  }
end

local models = db.query([[
  SELECT name, hf_repo_id, hf_revision
    FROM registered_models
   ORDER BY name
]])

for _, model in ipairs(models) do
  if model.hf_repo_id ~= nil and model.hf_revision ~= nil then
    local url = "https://huggingface.co/" .. model.hf_repo_id
        .. "/resolve/" .. model.hf_revision .. "/config.json"
    local meta = normalize(json.decode(http.get(url)))

    db.update(
      "UPDATE model_versions SET " ..
      "hf_architecture = " .. sql_quote(meta.architecture) .. ", " ..
      "hf_model_type = " .. sql_quote(meta.model_type) .. ", " ..
      "hf_hidden_size = " .. sql_number(meta.hidden_size) .. ", " ..
      "hf_num_layers = " .. sql_number(meta.num_layers) .. ", " ..
      "hf_num_heads = " .. sql_number(meta.num_heads) .. " " ..
      "WHERE model_name = " .. sql_quote(model.name)
    )
  end
end
LUA

echo "Implemented ${target}"

-- V003: backfill normalized Hugging Face Hub config metadata onto each registered
-- model's versions.
--
-- Each registered model has a pinned Hugging Face Hub repo/revision (hf_repo_id,
-- hf_revision). For every registered model, fetch its config.json through the http
-- helper, pull out the architecture / model type / hidden size / layer count /
-- attention-head count, and write those onto every one of that model's version rows
-- (hf_architecture, hf_model_type, hf_hidden_size, hf_num_layers, hf_num_heads).
--
-- This migration must not disturb any version's existing lineage (source_run_id /
-- parent_version), and must be safe to re-apply without changing its own output.

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

local models = db.query([[
  SELECT name, hf_repo_id, hf_revision
    FROM registered_models
   ORDER BY name
]])

for _, model in ipairs(models) do
  -- TODO: fetch this model's pinned Hub config via http.get, decode it with
  -- json.decode, and backfill hf_architecture / hf_model_type / hf_hidden_size /
  -- hf_num_layers / hf_num_heads onto this model's rows in model_versions.
end

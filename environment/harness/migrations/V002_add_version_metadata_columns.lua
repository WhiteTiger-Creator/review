-- V002: schema for the resolved-architecture backfill.
--
-- model_architecture is keyed by the architecture fingerprint, not by model name: two
-- registered models that resolve to the same architecture share one row. model_versions
-- references it through hf_architecture_fingerprint (already present in the seed, carrying
-- stale values from an abandoned earlier backfill).
--
-- V003 populates both. It never creates schema, so it can be re-applied freely.

db.update("ALTER TABLE registered_models ADD COLUMN hf_resolved_commit VARCHAR(64)")

db.update([[
  CREATE TABLE model_architecture (
      fingerprint              VARCHAR(64) PRIMARY KEY,
      architecture             VARCHAR(128),
      model_type               VARCHAR(64),
      hidden_size              INT,
      num_layers               INT,
      num_heads                INT,
      num_kv_heads             INT,
      head_dim                 INT,
      ffn_dim                  INT,
      attention_variant        VARCHAR(8),
      total_param_count        BIGINT,
      active_param_count       BIGINT,
      kv_cache_bytes_per_token BIGINT
  )
]])

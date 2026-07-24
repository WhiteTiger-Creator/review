-- V002: add the per-version Hugging Face config columns that V003 backfills. Versions
-- start with NULL metadata; V003 fills them in from the fetched Hub config.

db.update("ALTER TABLE model_versions ADD COLUMN hf_architecture VARCHAR(64)")
db.update("ALTER TABLE model_versions ADD COLUMN hf_model_type VARCHAR(64)")
db.update("ALTER TABLE model_versions ADD COLUMN hf_hidden_size INT")
db.update("ALTER TABLE model_versions ADD COLUMN hf_num_layers INT")
db.update("ALTER TABLE model_versions ADD COLUMN hf_num_heads INT")

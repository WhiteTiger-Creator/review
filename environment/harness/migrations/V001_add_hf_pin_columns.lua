-- V001: pin each registered model to a Hugging Face Hub repo + revision and record the
-- serving framework. These pins tell V003 which Hub config to fetch for each model.

db.update("ALTER TABLE registered_models ADD COLUMN framework VARCHAR(32)")
db.update("ALTER TABLE registered_models ADD COLUMN hf_repo_id VARCHAR(128)")
db.update("ALTER TABLE registered_models ADD COLUMN hf_revision VARCHAR(64)")

db.update([[
  UPDATE registered_models
     SET framework = 'transformers', hf_repo_id = 'acme/qa-encoder-base', hf_revision = 'v1.2.0'
   WHERE name = 'qa-encoder'
]])

db.update([[
  UPDATE registered_models
     SET framework = 'transformers', hf_repo_id = 'acme/sentiment-distil', hf_revision = 'v3.0.1'
   WHERE name = 'sentiment-classifier'
]])

db.update([[
  UPDATE registered_models
     SET framework = 'transformers', hf_repo_id = 'acme/summarizer-large', hf_revision = 'v2.5.0'
   WHERE name = 'summarizer'
]])

db.update([[
  UPDATE registered_models
     SET framework = 'transformers', hf_repo_id = 'acme/code-gpt', hf_revision = 'v0.9.4'
   WHERE name = 'code-generator'
]])

db.update([[
  UPDATE registered_models
     SET framework = 'transformers', hf_repo_id = 'acme/vl-caption', hf_revision = 'v1.0.0'
   WHERE name = 'vision-captioner'
]])

db.update([[
  UPDATE registered_models
     SET framework = 'transformers', hf_repo_id = 'acme/translator-t5', hf_revision = 'v1.1.0'
   WHERE name = 'translator'
]])

db.update([[
  UPDATE registered_models
     SET framework = 'transformers', hf_repo_id = 'acme/embed-mistral', hf_revision = 'v0.4.2'
   WHERE name = 'embedding-retriever'
]])

db.update([[
  UPDATE registered_models
     SET framework = 'transformers', hf_repo_id = 'acme/audio-wav2vec', hf_revision = 'v2.0.0'
   WHERE name = 'audio-classifier'
]])

db.update([[
  UPDATE registered_models
     SET framework = 'transformers', hf_repo_id = 'acme/rerank-falcon', hf_revision = 'v1.0.0'
   WHERE name = 'reranker'
]])

-- V001: pin each registered model to a Hugging Face Hub repo and revision tag.
--
-- The revision recorded here is a *tag*, not a commit. Tags move; the Hub resolves a tag
-- to the commit it currently points at through its revision API. V003 is responsible for
-- resolving each pin and recording the commit it resolved to.

db.update("ALTER TABLE registered_models ADD COLUMN hf_repo_id VARCHAR(128)")
db.update("ALTER TABLE registered_models ADD COLUMN hf_revision VARCHAR(64)")

local pins = {
  {"qa-encoder",          "acme/qa-encoder-base",   "v1.2.0"},
  {"sentiment-classifier","acme/sentiment-distil",  "v3.0.1"},
  {"summarizer",          "acme/summarizer-pegasus","v2.5.0"},
  {"code-generator",      "acme/code-gpt",          "v0.9.4"},
  {"vision-captioner",    "acme/vl-caption",        "v1.0.0"},
  {"translator",          "acme/translator-t5x",    "v1.1.0"},
  {"embedding-retriever", "acme/embed-mistral",     "v0.4.2"},
  {"audio-classifier",    "acme/audio-wav2vec",     "v2.0.0"},
  {"reranker",            "acme/rerank-falcon",     "v1.0.0"},
  {"chat-assistant",      "acme/chat-moe",          "v0.2.0"},
  {"doc-classifier",      "acme/doc-untied",        "v1.0.0"},
  {"doc-classifier-lite", "acme/doc-tied",          "v1.0.0"},
  {"instruct-tuned",      "acme/instruct-mistral",  "v3.1.0"},
  {"gemma-scorer",        "acme/gemma-scorer",      "v1.4.0"},
  {"legacy-forecaster",   "acme/legacy-arima",      "v0.1.0"},
  {"speech-tagger",       "acme/mamba-tagger",      "v0.3.0"},
  {"ocr-reader",          "acme/ocr-precedence",    "v2.2.0"},
  {"entity-linker",       "acme/entity-dangelo",    "v1.0.0"},
  {"long-context",        "acme/long-ctx",          "v4.0.0"},
}

for _, pin in ipairs(pins) do
  db.update(
    "UPDATE registered_models SET hf_repo_id = '" .. pin[2] ..
    "', hf_revision = '" .. pin[3] .. "' WHERE name = '" .. pin[1] .. "'"
  )
end

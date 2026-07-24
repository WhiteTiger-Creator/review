"""Sealed data service (compiled to .pyc; this .py source is never shipped in the
final image). Serves the pinned seed SQL and Hugging Face config fixtures over a
localhost-only HTTP endpoint so the Java harness can reach them without the agent
being able to read them as plain files. See LuaMigrationBridge/SeedDatabaseLoader/
HubConfigClient for the callers. Also tracks which config URLs have actually been
fetched (via /hf-config), so the verifier can confirm a migration genuinely called
http.get for every pinned model instead of reconstructing the answer some other way.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_HOST = "127.0.0.1"
_PORT = 8743

# URLs actually queried through /hf-config since the last /reset. Reset before each
# graded harness run so the check reflects that specific run, not a whole session.
_fetched_urls = set()

_SEED_SQL = "-- MLflow model-registry seed database.\n-- Base schema + seed rows as captured from the source registry. Migrations V001..V003\n-- evolve this schema and backfill Hugging Face Hub metadata on top of it.\n\nCREATE TABLE registered_models (\n    name          VARCHAR(128) PRIMARY KEY,\n    created_time  BIGINT       NOT NULL,\n    description   VARCHAR(512)\n);\n\nCREATE TABLE model_versions (\n    model_name     VARCHAR(128) NOT NULL,\n    version        INT          NOT NULL,\n    source_run_id  VARCHAR(64)  NOT NULL,\n    parent_version INT,\n    current_stage  VARCHAR(32)  NOT NULL,\n    PRIMARY KEY (model_name, version),\n    FOREIGN KEY (model_name) REFERENCES registered_models(name)\n);\n\n-- Ten registered models. Note that registration (created_time) order deliberately\n-- differs from alphabetical name order.\nINSERT INTO registered_models (name, created_time, description) VALUES\n    ('qa-encoder',           1700000000, 'Extractive QA sentence encoder'),\n    ('sentiment-classifier', 1700000100, 'Binary sentiment classifier'),\n    ('summarizer',           1700000200, 'Abstractive summarizer'),\n    ('code-generator',       1700000300, 'Code generation transformer'),\n    ('vision-captioner',     1700000400, 'Vision-language caption generator'),\n    ('translator',           1700000500, 'Encoder-decoder translation model'),\n    ('embedding-retriever',  1700000600, 'Dense passage retrieval embedding model'),\n    ('audio-classifier',     1700000700, 'Audio event classification model'),\n    ('reranker',             1700000800, 'Cross-encoder reranking model'),\n    ('anomaly-detector',     1700000900, 'Time-series anomaly detection model');\n\n-- qa-encoder lineage: v1 root, v2 promoted from v1.\nINSERT INTO model_versions (model_name, version, source_run_id, parent_version, current_stage) VALUES\n    ('qa-encoder', 1, 'run-qa-0001', NULL, 'Archived'),\n    ('qa-encoder', 2, 'run-qa-0002', 1,    'Production');\n\n-- sentiment-classifier lineage: single root version.\nINSERT INTO model_versions (model_name, version, source_run_id, parent_version, current_stage) VALUES\n    ('sentiment-classifier', 1, 'run-sent-0001', NULL, 'Production');\n\n-- summarizer lineage: v1 root, v2 fork of v1, v3 promoted from v2.\nINSERT INTO model_versions (model_name, version, source_run_id, parent_version, current_stage) VALUES\n    ('summarizer', 1, 'run-sum-0001', NULL, 'Archived'),\n    ('summarizer', 2, 'run-sum-0002', 1,    'Staging'),\n    ('summarizer', 3, 'run-sum-0003', 2,    'Production');\n\n-- code-generator lineage: v1 root, v2 promoted from v1.\nINSERT INTO model_versions (model_name, version, source_run_id, parent_version, current_stage) VALUES\n    ('code-generator', 1, 'run-code-0001', NULL, 'Staging'),\n    ('code-generator', 2, 'run-code-0002', 1,    'Production');\n\n-- vision-captioner lineage: single root version.\nINSERT INTO model_versions (model_name, version, source_run_id, parent_version, current_stage) VALUES\n    ('vision-captioner', 1, 'run-vl-0001', NULL, 'Production');\n\n-- translator lineage: v1 root, v2 promoted from v1.\nINSERT INTO model_versions (model_name, version, source_run_id, parent_version, current_stage) VALUES\n    ('translator', 1, 'run-tr-0001', NULL, 'Archived'),\n    ('translator', 2, 'run-tr-0002', 1,    'Production');\n\n-- embedding-retriever lineage: single root version.\nINSERT INTO model_versions (model_name, version, source_run_id, parent_version, current_stage) VALUES\n    ('embedding-retriever', 1, 'run-embed-0001', NULL, 'Production');\n\n-- audio-classifier lineage: v1 root, v2 fork of v1, v3 promoted from v2.\nINSERT INTO model_versions (model_name, version, source_run_id, parent_version, current_stage) VALUES\n    ('audio-classifier', 1, 'run-audio-0001', NULL, 'Archived'),\n    ('audio-classifier', 2, 'run-audio-0002', 1,    'Staging'),\n    ('audio-classifier', 3, 'run-audio-0003', 2,    'Production');\n\n-- reranker lineage: v1 root, v2 promoted from v1.\nINSERT INTO model_versions (model_name, version, source_run_id, parent_version, current_stage) VALUES\n    ('reranker', 1, 'run-rerank-0001', NULL, 'Archived'),\n    ('reranker', 2, 'run-rerank-0002', 1,    'Production');\n\n-- anomaly-detector lineage: single root version. Deliberately never pinned to a\n-- Hugging Face Hub repo (framework/hf_repo_id/hf_revision stay NULL after V001) --\n-- not every registered model necessarily has a Hub checkpoint backing it.\nINSERT INTO model_versions (model_name, version, source_run_id, parent_version, current_stage) VALUES\n    ('anomaly-detector', 1, 'run-anomaly-0001', NULL, 'Production');\n"

_HF_CONFIGS = {
    'https://huggingface.co/acme/qa-encoder-base/resolve/v1.2.0/config.json': '{"architectures": ["BertModel"], "model_type": "bert", "hidden_size": 736, "num_hidden_layers": 10, "num_attention_heads": 11, "vocab_size": 29184}',
    'https://huggingface.co/acme/sentiment-distil/resolve/v3.0.1/config.json': '{"architectures": ["DistilBertForSequenceClassification"], "model_type": "distilbert", "dim": 560, "n_layers": 5, "n_heads": 7, "vocab_size": 27462}',
    'https://huggingface.co/acme/summarizer-large/resolve/v2.5.0/config.json': '{"architectures": ["BartForConditionalGeneration"], "model_type": "bart", "hidden_size": 960, "num_hidden_layers": 18, "num_attention_heads": 15, "vocab_size": 48892}',
    'https://huggingface.co/acme/code-gpt/resolve/v0.9.4/config.json': '{"architectures": ["GPT2LMHeadModel"], "model_type": "gpt2", "n_embd": 1152, "n_layer": 30, "n_head": 18, "vocab_size": 49664}',
    'https://huggingface.co/acme/vl-caption/resolve/v1.0.0/config.json': '{"architectures": ["VisionEncoderDecoderModel"], "model_type": "vision-encoder-decoder", "is_encoder_decoder": true, "text_config": {"model_type": "gpt2", "hidden_size": 832, "num_hidden_layers": 15, "num_attention_heads": 13}, "vision_config": {"model_type": "vit", "image_size": 224, "patch_size": 16, "num_channels": 3}}',
    'https://huggingface.co/acme/translator-t5/resolve/v1.1.0/config.json': '{"architectures": ["T5ForConditionalGeneration"], "model_type": "t5", "d_model": 704, "num_layers": 10, "num_decoder_layers": 5, "num_heads": 11, "vocab_size": 31104}',
    'https://huggingface.co/acme/embed-mistral/resolve/v0.4.2/config.json': '{"architectures": ["MistralModel"], "model_type": "mistral", "hidden_size": 3840, "num_hidden_layers": 30, "num_attention_heads": 30, "num_key_value_heads": 6, "vocab_size": 30720}',
    'https://huggingface.co/acme/audio-wav2vec/resolve/v2.0.0/config.json': '{"architectures": [], "model_type": "wav2vec2", "hidden_size": 672, "num_hidden_layers": 9, "num_attention_heads": 14, "vocab_size": 34}',
    'https://huggingface.co/acme/rerank-falcon/resolve/v1.0.0/config.json': '{"architectures": ["FalconForSequenceClassification"], "model_type": "falcon", "hidden_size": 4160, "num_hidden_layers": 28, "head_dim": 80, "vocab_size": 63616}',
}


class _Handler(BaseHTTPRequestHandler):
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
        if parsed.path == "/health":
            self._send(200, "ok")
            return
        if parsed.path == "/seed":
            self._send(200, _SEED_SQL, "text/plain; charset=utf-8")
            return
        if parsed.path == "/reset":
            _fetched_urls.clear()
            self._send(200, "ok")
            return
        if parsed.path == "/fetched-urls":
            self._send(200, json.dumps(sorted(_fetched_urls)), "application/json")
            return
        if parsed.path == "/hf-config":
            qs = parse_qs(parsed.query)
            url = (qs.get("url") or [None])[0]
            config_json = _HF_CONFIGS.get(url)
            if config_json is None:
                self._send(404, "not pinned")
                return
            _fetched_urls.add(url)
            self._send(200, config_json, "application/json")
            return
        self._send(404, "not found")


def main():
    server = ThreadingHTTPServer((_HOST, _PORT), _Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()

Benchmark records use JSON Lines. Each record has id, modality, prompt, answer, options, metadata, canary, age_months, embedding, and paraphrases. A paraphrase has text, distance, and embedding fields. Corpus records have id, text, and embedding fields.

Adjudicated panel records also use JSON Lines. Each row has id, modality, a contaminated flag that is zero or one, and the nine evidence fields the panel module names, all as numbers.

The audit configuration names benchmark and corpus paths, an HTTP endpoint, output paths, probe settings, calibration settings, and cleaning limits. Probe settings contain integer seeds and arrays for the six study axes. Calibration settings contain panel_paths and a penalties array. Cleaning limits contain risk_limit, minimum_retention, and minimum_per_modality.

The configured endpoint accepts an HTTP POST with a JSON object containing item_id, prompt, probe_kind, answer_format, framing, temperature, seed, option_order, canary, paraphrase_distance, canary_rarity, and benchmark_age.

A successful response is JSON with text, logprob, metadata_echo, and returned_canary. The text is the model completion, logprob is a finite number, metadata_echo is an object, and returned_canary is a string. Any other response is malformed.

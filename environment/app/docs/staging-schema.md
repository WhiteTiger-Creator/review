# staging schema (tab-separated state files)

All files live under /app/state, one row per line, fields tab-separated,
rows sorted by (batch_id, payload_id) and, where present, a numeric index.
Binary columns are lowercase hex.

## payloads.tsv

batch_id, payload_id, ecc_level (L/M/Q/H), text_hex

## plans.tsv

batch_id, payload_id, ecc_level, version, cci_class (0 or 1), total_bits,
segment_count

## segments.tsv

batch_id, payload_id, segment_index, mode (numeric/alphanumeric/byte),
char_count, bit_count (header plus data bits for the plan's class)

## codewords.tsv

batch_id, payload_id, codeword_count, data_codewords_hex

## blocks.tsv

batch_id, payload_id, block_index (global, zero-based), group (1 or 2),
data_len, data_hex, ecc_hex

## streams.tsv

batch_id, payload_id, stream_len, stream_hex, stream_sha256

## tournament.tsv

batch_id, payload_id, mask_id (0..7), penalty_runs, penalty_blocks,
penalty_finder, penalty_balance, penalty_total, winner (1 on exactly one row
per payload, else 0)

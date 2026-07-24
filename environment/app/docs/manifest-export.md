# manifest export contract

emit-labels renders one PGM per payload and publishes
/app/output/labels/label-run-manifest.json from persisted state rows only.

## label PGM

Plain (P2) PGM. Each module is rendered as an module_scale x module_scale
square (composer.toml, default 8), dark modules as 0 and light as 255, with
a quiet zone of quiet_modules (default 4) light modules on all four sides.
Image width and height are (size + 2 * quiet_modules) * module_scale.
File name: batch_id-payload_id.pgm under /app/output/labels.

## manifest

JSON object with schema label-run/1, symbol_count, and a symbols array in
(batch_id, payload_id) order. Each entry carries batch_id, payload_id,
ecc_level, version, size, mask (the tournament winner), segment_count,
total_bits, ec_per_block, group1_blocks, group1_data_codewords,
group2_blocks, group2_data_codewords, interleaved_sha256 (from streams.tsv),
matrix_sha256, and label_pgm (absolute path).

matrix_sha256 is the SHA-256 of the final masked matrix serialized row-major
as ASCII 1 for dark and 0 for light, no separators.

Repeated emit-labels over unchanged state must produce byte-identical files.
The command never re-reads the inbox; changing or unsetting the inbox
override at emit time must not change output.

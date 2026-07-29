# Duty mix, auth_stamp, and replay seal

Duty mix constant is 0x631A31C0.

auth_stamp accumulates, in ascending row_id order,
rotl64(hop_key, R) xor fold_tag xor span_u64, then xors the duty mix, and
hex-encodes the result. Rotate width R is pad- and arm-dependent, then
latched to the annex epoch E from `/app/data/annex31/manifest.json`.
Train arm uses a fixed rotate width of one on every pad (R is always 1,
not the pad index). Hold arm starts from a pad base width (pad one uses
three, pad two uses five, pad three uses seven, pad four uses eleven) and
then adds E mod 5. Hold fold composition uses a different epoch modulus;
see `/app/docs/fold_home.md`.

Operator duty sketches such as `/app/output/side/duty.cache` and stamp
sketches such as `/app/output/side/stamp.soft` are aids only. They must
not freeze stamp rotate widths or stamp digests on a later regeneration.

hold_mesh is the xor of hop_key values for every hold arm row only.
fold_mesh is the xor of fold_tag values for every hold arm row only, in
ascending row_id order. replay_seal binds mesh_digest, auth_stamp, epoch E,
hold_mesh, and fold_mesh as
rotl64(mesh, 5) xor stamp xor (E left-shift 16) xor duty_mix xor
rotl64(hold_mesh, 3 plus (E mod 5)) xor rotl64(fold_mesh, 2 plus (E mod 7)),
then hex-encoded. The fold_mesh rotate width is 2 plus (E mod 7), not bare
E mod 7. Omitting fold_mesh, using bare E mod 7 for that rotate, or xoring
raw hold_mesh without the duty-modulus rotate, fails the seal contract. The
same seal_hex must appear in sol_run.replay_seal and in
`/app/output/replay_seal.json`. After E moves, hold hop_keys and hold folds
change, so hold_mesh, fold_mesh, and replay_seal must follow together. Mesh
composition itself is published in `/app/docs/out_fields.md`.

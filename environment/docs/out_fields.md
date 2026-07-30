# sol_run.json schema fields

Top-level object holds

- schema_version as integer, value 1
- mesh_digest as string, exactly 16 lowercase hex characters
- auth_stamp as string, exactly 16 lowercase hex characters
- replay_seal as string, exactly 16 lowercase hex characters
- rows as a JSON array (list) of row objects

Each row object holds

- row_id as string matching an annex31 packed row id
- hop_key as string, exactly 16 lowercase hex characters
- fold_tag as integer
- span_u64 as integer
- join_hex as string, exactly 16 lowercase hex characters
- arm as string, either train or hold

join_hex encodes hop_key xor fold_tag xor span_u64 xor arm_bit as 16 hex
digits for train rows. The arm_bit term is the integer 0 when arm is train
and the integer 1 when arm is hold. For hold rows, that same xor also mixes
((((E and 0xff) left-shift 8) or (pad and 0xff)) xor ((E mod 3) left-shift 16)),
where E is the annex manifest epoch and pad is the row pad code. A bare
(E and 0xff) join mix, or the pad nibble without the (E mod 3) left-shift 16
term, is not enough.

train_mesh equals the xor of train-arm hop_key values in ascending row_id order.
hold_mesh equals the xor of hold-arm hop_key values in the same order.
fold_mesh equals the xor of hold-arm fold_tag values in the same order.
mesh_digest is computed as rotl64(train_mesh xor hold_mesh, 1 plus (E mod 3)),
hex-encoded. The rotate width is 1 plus (E mod 3), not bare E mod 3. Rotate
the combined train xor hold mesh; do not rotate only one side before the xor.
That modulus still matches the hold fold rotate latch modulus family, not the
stamp duty modulus.

auth_stamp and replay_seal identities are published in
`/app/docs/duty_home.md`. Side caches under `/app/output/side` are operator
aids only and must not freeze graded hops. Operator pins such as
`/app/output/side/mesh.pin`, duty sketches such as
`/app/output/side/duty.cache`, and stamp sketches such as
`/app/output/side/stamp.soft` must not alter graded mesh, stamp, or seal
identities.

A companion authority transcript `/app/output/replay_seal.json` must carry
schema_version 1, the annex epoch integer from
`/app/data/annex31/manifest.json`, and seal_hex matching sol_run.replay_seal.

Operator journal files under `/app/output/side/jrn` are described in
`/app/docs/jrn_home.md` and must not override graded stamp or seal authority.

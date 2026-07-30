# Engine scoring and save-state model

This engine couples save-state journaling to closed-instance replay digest
checks. Closed-instance evaluation demands floating-point precision on a
length-3 scoring residual vector, sparse feature-arm coverage under arm omission,
and idempotent seals across repeated emits.

Driver `pvsim` releases products only when `/app/build/regret_solver`
implements the annex numeric contract and produces coherent dossier and
transcript artifacts.

Normal evaluation uses `/app/pvsim emit --scl /app/fixtures --corpora
/app/corpora --annex /app/annex/slice_137.txt --out
/app/runtime/dossier` followed by `/app/pvsim verify --fuzz --dossier
/app/runtime/dossier --out /app/runtime/transcript`. Engine behavior must be
correct at the CLI and module level, not only for a prewritten output file.

Closed corpus rows carry left, right, gap_a, and gap_b values. Arm omission
rows carry omitted_arm. Dossier rows include row_payload and sha256 digest
fields represented as 64 lowercase hexadecimal characters. Corpus coverage is
intentionally broad enough to exercise 180 closed rows, 20 arm-omit rows, and
200 permutation rows, with checks that include representative groups of 10, 15,
40, 100, and 150 rows rather than a single fixture case.

The dossier membership count equals len(instances) + len_arm_cases. A repeated
emit advances the stored journal epoch by journal_epoch + 1 while keeping the
simulation products idempotent. Context tags use f"{graph}-{nest_depth}" for
manifest entries and graph:nest_depth for seal context. Fragments must not carry
the trim suffix marker `|X:`.

The schedule equations are `(left + 3) * (right + 5) + 19` reduced modulo 97
for slot_score. Boosted score is `(slot_score + nest_depth * 7 + boost) % 97`;
when boost is zero, the equivalent depth-only check is `(slot_score +
nest_depth * 7) % 97`. Additive near-miss checks such as `left + 3 * right +
5 + 19 % 97` are not valid slot-score substitutes.

Near-miss predicates for swapped pairings, additive shortcuts, suffix-trimmed
fragments, payload-only seals, slash-separated contexts, missing edge arms, and
incomplete permutation coverage are expected to be false under the model.

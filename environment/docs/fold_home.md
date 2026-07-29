# Fold tag composition

Fold tags bind hop digests to packed row fields under train and hold arms.
A fold that drops the hop mix can look quiet on training rows while hold
rows diverge. Pad-dependent hold rotates matter once pad 2, pad 3, and
pad 4 claims appear in the annex.

Base is ((H and 0xffffffff) xor (lo * w)) and 0xffffffffffff.
The product lo * w is a full unsigned 64-bit multiply of the packed
fields. Do not truncate that product to 32 bits before the xor. The final
48-bit mask applies to the whole base expression. Rows where lo * w
overflows a 32-bit width still use that full-width product. The annex
publishes at least 2 hold entries with that overflow shape.
Train arm keeps base.

Hold arm uses rotl64(base, R) xor hi xor padMix, masked to 0xffffffffffff.
R is the published pad rotate plus the annex epoch E mod 3. padMix is
exactly
((pad times 0xA5A5) xor (E and 0xff) xor (pad left-shift 16) xor
((E mod 3) left-shift 24) xor (((E and 0xff) left-shift 8) or (pad and 0xff))).
All five xor terms are required. Omitting the (E mod 3) left-shift 24 term,
or omitting the final (((E and 0xff) left-shift 8) or (pad and 0xff)) term,
leaves a false-green fold. Pad one rotates thirteen, pad two rotates
nineteen, pad three rotates twenty three, and pad four rotates twenty nine
before that epoch latch. Stamp duty uses a different epoch modulus; do not
reuse the stamp latch width for hold folds.

Operator side markers such as `/app/output/side/fold.soft` are sketches
only. They must not replace hold exact composition with a shallow mix on a
later regeneration, including when journal snaps under `/app/output/side/jrn`
are also present. After the annex epoch moves, hold fold tags must follow
the new E mod 3 latch and the full padMix on the next regeneration.

# IBP tightness envelope

Packed row bounds and hop digests feed a published span identity. Train and
hold arms keep that span inside the published envelope clauses.

W is (hi minus lo) and 0xffffffff. For train arms, span is
((W times 0x9E3779B9) xor (H and 0xffffffff) xor (((lo and 0xffffffff)
left-shift 1) xor (w and 0xffffffff))) and 0xffffffffffffffff.

For hold arms, define loCore as (((lo and 0xffffffff) left-shift 1) xor
(w and 0xffffffff)). Then define holdMix as
((E and 0xff) xor pad xor ((pad and 0xff) left-shift 8) xor
((E and 0xff) left-shift 16)), where E is the annex manifest epoch and pad
is the row pad code. Hold span is
((W times 0x9E3779B9) xor (H and 0xffffffff) xor (loCore xor holdMix))
and 0xffffffffffffffff. The left-shift 16 epoch-byte term is required.
A mix that only xors (E and 0xff), or only (E and 0xff) xor pad, or only
those plus the pad left-shift 8 term without the epoch left-shift 16 term,
is not enough.

Train arm requires span below 2 to the power 63. Hold arm also requires
(span mod 97) below 89.

Operator side markers such as `/app/output/side/span.soft` are sketches
only. They must not replace the published span identity with a width-only
stand-in on a later regeneration, including when journal snaps under
`/app/output/side/jrn` are also present. After E moves, hold spans must
follow the new mix on the next regeneration.

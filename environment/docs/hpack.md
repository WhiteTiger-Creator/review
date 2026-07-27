# HPACK interpretation-conflict witness contract

This document is the complete, authoritative contract for the task. It defines
the block wire format, the *spec-compliant reference decoder* that fixes ground
truth, the audited decoder's deviations from it, the *obligation* grammar you are
asked to satisfy, and the exact *witness* your program must emit. Grading follows
this document exactly.

The decoder under audit is the stripped binary at `evidence/decoder`; its
**observable behavior is the complete and authoritative definition** of the
audited decoder. Its source is not shipped — run the binary on blocks you craft
to characterize it. It reads a block file named on its first argument, prints one
`H <namehex> <valuehex>` line per emitted field, then `ACCEPT`, or `REJECT <n>`
where `n` is the number of fields emitted before a decode error. The reference and
audited decoders share one octet grammar and one Huffman code, and differ only in
the independent respects named under "Deviations under audit". You are not asked
to classify a given block. You are asked to **construct** blocks: given an
obligation describing an interpretation conflict, emit wire octets on which the
two decoders exhibit exactly that conflict.

## Block wire format

A block is a 4-octet big-endian unsigned integer — the initial dynamic-table
maximum size in octets, never exceeding the protocol maximum of 4096 — followed
by HPACK instruction octets. The instruction octets are decoded as below.

## Primitives

Integer primitive. Integers use an N-bit prefix (HPACK Section 5.1). If the value
is below 2^N minus 1 it is held in the prefix. Otherwise the prefix is all ones
and continuation octets follow: while an octet has its high bit set another
follows, and the value accumulates the low seven bits of each continuation octet
at increasing seven-bit shifts. At most six continuation octets appear in scope.

String primitive. A string literal is a one-octet flag-and-length group followed
by the string octets. The high bit of the first octet is the Huffman flag. The
remaining seven bits begin a 7-bit-prefix integer giving the number of octets
that follow. When the Huffman flag is 0 the octets are literal. When it is 1 the
octets are Huffman-encoded per HPACK Appendix B and Section 5.2 (see below).

Huffman strings. The reference decodes Huffman octets with the RFC 7541 Appendix B
canonical code, then validates padding per Section 5.2: any trailing bits that do
not complete a symbol are padding, and the reference rejects the string unless the
padding is at most 7 bits, consists of the most-significant bits of the EOS code
(i.e. all ones), and no decoded symbol is the EOS symbol.

## Static table

The static table has 61 entries at combined indices 1 through 61. Index 62 and
above address the dynamic table. The entries are, in order: :authority;
:method GET; :method POST; :path /; :path /index.html; :scheme http;
:scheme https; :status 200; :status 204; :status 206; :status 304; :status 400;
:status 404; :status 500; accept-charset; accept-encoding "gzip, deflate";
accept-language; accept-ranges; accept; access-control-allow-origin; age; allow;
authorization; cache-control; content-disposition; content-encoding;
content-language; content-length; content-location; content-range; content-type;
cookie; date; etag; expect; expires; from; host; if-match; if-modified-since;
if-none-match; if-range; if-unmodified-since; last-modified; link; location;
max-forwards; proxy-authenticate; proxy-authorization; range; referer; refresh;
retry-after; server; set-cookie; strict-transport-security; transfer-encoding;
user-agent; vary; via; www-authenticate. Entries listed without a value have the
empty value.

## Representations (reference decoder)

Each instruction begins at an octet whose high bits select the representation.

- Indexed Header Field, high bit 1, 7-bit-prefix index. Emits the entry at that
  combined index. Index 0 is a decode error. The dynamic table is unchanged.
- Literal Header Field with Incremental Indexing, high bits 01, 6-bit-prefix name
  index. Name index 0 means the name is a following string literal; otherwise the
  name is that entry's name. The value is a following string literal. The field is
  emitted, then inserted into the dynamic table.
- Literal Header Field without Indexing, high bits 0000, and Literal Header Field
  Never Indexed, high bits 0001, both with a 4-bit-prefix name index resolved the
  same way, each followed by a value string literal. The field is emitted. The
  reference changes the dynamic table for neither.
- Dynamic Table Size Update, high bits 001, 5-bit-prefix new maximum, which may
  not exceed 4096. It sets the current maximum and evicts as below. Nothing is
  emitted.

## Dynamic table maintenance (reference decoder)

The dynamic table holds inserted fields most-recent first; a newly inserted field
takes combined index 62 and older entries take higher indices. The size of an
entry is the length of its name in octets plus the length of its value in octets
plus 32. The size of the table is the sum of its entry sizes. Before inserting a
field, entries are evicted from the oldest end until the table size is at most the
current maximum minus the new entry size, or the table is empty; a field whose
size exceeds the current maximum empties the table and adds nothing. A size update
evicts from the oldest end until the table size is at most the new maximum.

Resolving a combined index at or below 61 reads the static table; a higher index
reads the dynamic entry at that position, and an index beyond the current dynamic
table is a decode error. Any decode error rejects the whole block: the decoder
emits the fields produced before the error and stops.

## Deviations under audit

The audited decoder (`evidence/decoder`) departs from the reference in a small
number of independent respects. Each departure is named by one obligation
mechanism token — `overhead`, `never`, `huffpad`, `sizeupdate`, or `minint` — but
this document does not tell you what any of them does. The binary's observed
behavior is the authoritative definition of the audited decoder. Determine by
probing it exactly how, where, and under which representation each named departure
changes the emitted-field sequence relative to the reference specified above, and
which decoder computation each one isolates.

Four of the departures make the audited decoder *more permissive* than the
reference (it retains or accepts where the reference drops or rejects); one makes
it *stricter* (it rejects a block the reference accepts). Both directions of
conflict are therefore reachable.

For a set of deviations S, let `decode_S` be the decoder that applies exactly the
deviations in S over the reference. `decode_{}` is the reference; the audited
decoder applies every departure,
`decode_{overhead,never,huffpad,sizeupdate,minint}`; `decode_{d}` applies one
departure alone; and `decode_S` for a larger S applies exactly those together.

## Divergence and outcome

Each decoder run over a block produces an ordered sequence of emitted (name,
value) fields and either accepts the whole block or rejects it after emitting a
prefix. For two runs, the **first divergence position** is the number of leading
emitted fields on which they agree (a field present in one run and absent in the
other counts as a disagreement). The **outcome** of a reference/audited pair is
`both_accept` when neither rejects, `reference_reject` when the reference rejects
and the audited decoder emits a field at the divergence position that the
reference does not, and `audited_reject` symmetrically.

## Obligations

An obligation is one line of `key=value` tokens:

```
mech=<token> outcome=<both_accept|reference_reject|audited_reject> pos=<int> max=<int> maxlen=<int> huff=<required|none>
```

- `mech` names the audited deviation that must cause the conflict. It is either a
  single token (`overhead`, `never`, `huffpad`, `sizeupdate`, or `minint`) or a
  `+`-joined set of them (for example `never+sizeupdate`). A joint token requires
  a conflict that arises only from those deviations acting *together*: no single
  named deviation, and no proper subset, may reproduce it on its own.
- `outcome` is the required reference/audited outcome as defined above.
- `pos` is the exact first-divergence position (a decimal integer, counting from 0).
- `max` is the initial dynamic-table maximum your block's 4-octet header must carry.
- `maxlen` is the maximum length in octets of the whole block, header included.
- `huff` is `required` when at least one Huffman-encoded string must appear in the
  block; `huffpad` obligations require a Huffman string intrinsically.

## Graded obligation families

Grading draws obligations only from the `(mech, outcome)` families below. This
fixes the *scope* of what is asked; it does not tell you how to build any
witness — that still requires reverse-engineering the deviations from the binary
and constructing the exact divergence. No other combination is graded. Pairings
outside this list — for example `never` with `audited_reject`, `minint` with
`reference_reject`, or any `overhead`, `huffpad`, or `sizeupdate` with
`both_accept` — are not part of the battery and need not be constructed.

| `mech`             | `outcome`          |
|--------------------|--------------------|
| `never`            | `both_accept`      |
| `never`            | `reference_reject` |
| `overhead`         | `reference_reject` |
| `huffpad`          | `reference_reject` |
| `sizeupdate`       | `reference_reject` |
| `minint`           | `audited_reject`   |
| `never+sizeupdate` | `reference_reject` |

`minint` and `never+sizeupdate` are the only families carrying, respectively,
the `audited_reject` outcome and a joint `mech`. Divergence positions (`pos`)
are small — the conflict is placed near the front of the emitted-field sequence,
and `pos=0` does occur (for the `minint` and `huffpad` families). Every
obligation's `pos`, `max`, `maxlen`, and `huff` are still honored exactly as
defined above.

## The witness (program output)

Your program reads the obligation from the file named on its first argument and
prints exactly one line: the lowercase hexadecimal encoding of a witness block,
no `0x` prefix, no separators, and nothing else on standard output or standard
error. The witness is accepted only when **all** of the following hold, checked by
an independent verifier that recomputes every decoder itself:

1. The block is at least 4 octets and at most `maxlen` octets, and its 4-octet
   header equals `max`.
2. `decode_{}` (reference) and `decode_{overhead,never,huffpad,sizeupdate,minint}`
   (audited) first diverge at emitted position exactly `pos`; call the field
   present there `w`.
3. The outcome of that reference/audited pair equals `outcome`.
4. If `huff=required` or `mech=huffpad`, at least one Huffman-flagged string is
   present in the block.
5. Mechanism isolation. Let `S` be the set of deviations `mech` names (one
   element for a single token, several for a `+`-joined token). **Sufficiency:**
   `decode_{}` and `decode_S` first diverge at position `pos` with the same field
   `w` — the named deviations, acting together, reproduce the exact conflict.
   **Minimality:** for every proper subset `S' ⊂ S`, `decode_{}` and `decode_S'`
   do not diverge at `pos` with `w` — no smaller combination reproduces it, so
   every named deviation genuinely contributes. **Necessity:** for every `d ∈ S`,
   `decode_{}` and `decode_{overhead,never,huffpad,sizeupdate,minint}\{d}` do not
   diverge at `pos` (they agree there, or first diverge later) — removing any one
   named deviation from the audited decoder heals the conflict at `pos`.

A witness that diverges by exploiting a different deviation than those in `mech`,
that a proper subset of `mech` already reproduces, or that lands at the wrong
position or outcome, fails.

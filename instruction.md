This is an offensive HTTP/2 security exercise. A vulnerable HPACK header-block
decoder is staged as immutable evidence at /app/environment/evidence/decoder — a
stripped black-box binary whose source is withheld; you may execute it but must
not modify it. It shares the octet grammar and RFC 7541 Huffman code of a
spec-compliant peer, yet mismanages shared decoder state so the two decoders
reconstruct different header-field sequences from identical well-formed wire
octets. That interpretation conflict (CWE-436) is a header desynchronization
primitive — the basis of HTTP/2 request smuggling and cache poisoning. Its
observed behavior is the authoritative definition of the audited decoder;
what must be discovered is how it deviates from the spec-compliant reference
documented for you and the exact conditions under which each deviation manifests.
Several departures make it more permissive; one makes it stricter, and some
conflicts arise only when departures act together.

Your job is to weaponize the divergence, not classify it. You are handed a
sequence of exploitation obligations. Each names the audited deviation — or a
combination that must act jointly — as the required root cause and pins the
accept/reject outcome, the exact emitted-field position of the first
disagreement, the dynamic-table maximum your block must carry, a length ceiling,
and any Huffman requirement. For each, craft one well-formed attack block on which
the two decoders diverge in exactly that way and no other. The verifier recomputes
both decoders and every deviation subset to confirm the conflict fires at the
named position and outcome and is attributable to exactly the named deviations.

The wire format, reference decoder, obligation grammar, and witness contract are
in /app/environment/docs; grading follows them exactly. Fresh obligations are
graded, so construct per obligation. Deliver your payload generator as a Rust
program in /app/environment/analysis, built with cargo build --release --locked to
produce the `synth` binary. The standard library is the only dependency and there
is no network.

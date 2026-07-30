# Request and storage boundary

Service configuration standard for shared edge-cache admission. Operators confirm via client responses, origin access logs, and process inspection.

## Hosts

A request is routable only when Host, after stripping a numeric port and lowercasing, is exactly one of:

- `releases.aurora.invalid`
- `releases.basalt.invalid`

Missing, malformed, or unsupported hosts receive status `421 Misdirected Request` with `X-Edge-State: SYNTH` and must not contact either origin. Do not use `404` for an unknown Host. The canonical host is what hashing and backend delivery use.

## URL and encoding

Semantically identical query parameter orderings share one object (native query sorting). A trailing bare `?` is removed. Different parameter values stay distinct objects. Do not strip marketing parameters or rewrite percent-encoding.

When `Accept-Encoding` contains `gzip` as a token (case-insensitive), reduce the header to exactly the string `gzip` before hashing and before contacting an origin. Otherwise remove `Accept-Encoding` entirely. Cache identity uses that post-normalization state: either the literal value `gzip`, or the absent-header state. Those two states must never share an object.

Normalize first, then hash, and reduce the header on the request before any backend fetch so `Vary: Accept-Encoding` keys see the same post-reduction value. Hashing the raw client header (for example `gzip, deflate, br`) keeps variants on different keys and fails the contract below.

Observable encoding outcomes on the same URL and host:

- `Accept-Encoding: gzip, deflate, br` then `Accept-Encoding: gzip` → first is `MISS`, second is `HIT` (same object)
- a later request with no `Accept-Encoding` header → `MISS` (different object), even if a gzip object already exists

Illustrative admission fragment (header value only; complete VCL is out of scope here):

```vcl
if (req.http.Accept-Encoding ~ "(?i)gzip") {
    set req.http.Accept-Encoding = "gzip";
} else {
    unset req.http.Accept-Encoding;
}
```

In `vcl_hash`, hash the host, the normalized URL, and `req.http.Accept-Encoding` when it is still set after the reduction above. Do not invent a stand-in empty string for the absent-header state.

Origins may send `Vary: Accept-Encoding`; after request-side normalization that response remains storage-eligible and must not be treated as an unapproved Vary. Do not refuse caching solely because the origin varied on Accept-Encoding.

## Cache key

Cache identity includes canonical host, normalized URL, and the normalized `Accept-Encoding` state above. Objects for one supported host must never satisfy the other.

## Methods and forced pass

Only `GET` and `HEAD` may use or populate shared storage. Other ordinary methods pass to an origin. `PURGE` and `BAN` follow the invalidation standard.

A `GET`/`HEAD` must pass (and not use or fill shared storage) when any of these is present:

- `Authorization`
- any `Cookie`
- `Range`
- request `Cache-Control` whose value contains the token `no-cache` or `no-store` (case-insensitive)
- request `Pragma` whose value contains the token `no-cache` (case-insensitive)

Match against the header **value** only — never against a string that includes the characters `Pragma:`. A value of exactly `no-cache` must force PASS.

`Pragma` is independent of `Cache-Control`. A GET that carries only `Pragma: no-cache` (no Authorization, Cookie, Range, or Cache-Control) must still return `X-Edge-State: PASS` and must not seed shared storage for that URL. A following plain GET of the same URL is then `MISS`.

Illustrative admission fragment:

```vcl
if (req.http.Cache-Control ~ "(?i)no-cache" ||
    req.http.Cache-Control ~ "(?i)no-store" ||
    req.http.Pragma ~ "(?i)no-cache") {
    return (pass);
}
```

Passed responses use `X-Edge-State: PASS`.

## Storage eligibility

Only a `200` to an eligible `GET`/`HEAD` may enter shared storage. Responses must not carry `Set-Cookie`, `Cache-Control` private/no-store/no-cache, `Vary: *`, or any `Vary` other than exactly `Accept-Encoding` (case/OWS insensitive). Ineligible responses are never reused.

Eligible origins send `Cache-Control: public, max-age=1` and one `X-Artifact-Class` of `stable`, `candidate`, `metadata`, or `large`. That class value is the class identity for storage and class bans. Missing or unknown class makes the response uncacheable. Any internal invalidation metadata attached to stored objects must not appear on client responses.

## Edge state

Every client response through Varnish carries exactly one of:

```text
X-Edge-State: MISS
X-Edge-State: HIT
X-Edge-State: PASS
X-Edge-State: GRACE
X-Edge-State: SYNTH
```

First stored fetch is `MISS`; fresh reuse is `HIT`; forced pass is `PASS`; stale outage service is `GRACE`; locally generated failures are `SYNTH`. Origin `X-Origin-Node` remains visible on backend responses.

## Conditionals and large objects

A cache-resident object with matching `If-None-Match` returns `304` with an empty body and accurate edge state. Large objects stream during fetch and become reusable after successful completion. The large fixture is six MiB.

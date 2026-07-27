# Acme Wallet Presentation Profile WP-1

Status: adopted, revision 4. Owner: Wallet Platform.

This profile is what our wallet agrees with the partner verifiers that consume our credentials. It
covers the selectively disclosable credentials our issuer mints, how the wallet decides what a
credential may be used for, and what a released presentation looks like on the wire. It follows the
SD-JWT family of specifications; the sections below only record the choices this deployment makes
where the underlying specifications leave room, and the exact wording of anything the partners test
us on.

## 1. Stored credentials

Every credential the wallet holds sits in its own `*.sdjwt` file inside the credential directory.
The file holds one line: the credential in issuance form,

```
<Issuer-signed JWT>~<Disclosure>~<Disclosure>~ ... ~
```

with a trailing `~` and no key binding JWT. Every `~`-separated part, and every part of the compact
JWS, is unpadded base64url over the characters `A-Z a-z 0-9 - _`. The credential identifier is the
file name without the `.sdjwt` suffix.

A disclosure decodes to a JSON array. Three elements `[salt, claim name, claim value]` hide an
object member; two elements `[salt, claim value]` hide an array element. The digest of a disclosure
is `SHA-256` over the US-ASCII bytes of the disclosure exactly as it appears in the credential,
encoded base64url. Issuers vary in how they lay out the JSON inside a disclosure, so a digest is
only reproducible from the received characters.

The issuer-signed payload marks hidden data in two ways. An object carries an `_sd` member holding
an array of digests of the members hidden from it. An array carries, in place of a hidden element,
the object `{"...": "<digest>"}`. Both forms nest: the value inside a disclosure may itself contain
`_sd` members and `...` placeholders. The top-level payload member `_sd_alg` names the digest
algorithm; this profile only accepts `sha-256`, and treats the member as absent-means-`sha-256`.
`_sd` and `_sd_alg` never survive into the resolved credential.

## 2. Resolving a credential

Resolving means putting every disclosure the wallet holds back where it belongs. A disclosure whose
digest appears in an `_sd` array reinstates its claim name and value in the object that carried the
`_sd`; a disclosure whose digest appears in a `...` placeholder replaces that element of the array.

Issuers pad `_sd` arrays with decoy digests, so a digest that no held disclosure matches is simply
dropped, and a `...` placeholder that no held disclosure matches removes that element from the
array — the surviving elements keep their relative order. The reverse is not tolerated: the
credential is rejected when a disclosure is never consumed, when the same digest value occurs at
more than one place in the credential, when a two-element disclosure lands on an `_sd` entry or a
three-element one on a placeholder, when a disclosed member is named `_sd` or `...`, when `...`
appears as an ordinary object member, when `_sd` is anything other than an array of strings, or when
a disclosed member collides with a member the object already has.

A **claim path** names a place in the resolved credential: object members joined with `.`, array
elements written as `[index]` against the position the element has once the credential is fully
resolved. `residence.address.geo.lat` and `nationalities[1]` are claim paths.

## 3. Issuer keys

The issuer's keys are a JWK Set at `mp.jwt.verify.publickey.location`, read on every run. Following
the MicroProfile config contract, that location is a URL, which in production names the issuer's own
endpoint and on a host that mirrors the key set names the local copy. A published key is
usable here when it has a `kid`, is not published for encryption (`use` of `enc`), is an RSA key or
an EC key on `P-256`, and either omits `alg` or names one this profile verifies. A credential is
verified with the usable key whose `kid` matches the JOSE header, restricted to keys whose type and
`alg` can serve the header's algorithm — RSA for `RS256`, EC for `ES256`. A credential with no `kid`
is verified only when exactly one usable key can serve its algorithm. Key thumbprints reported to
operations are RFC 7638 thumbprints.

## 4. Acceptance ladder

Each credential gets the first status below that applies to it; the checks are ordered, so a
credential never reports a later failure than the earliest one it has.

| status | applies when |
|---|---|
| `malformed` | no trailing `~`, a part that is not unpadded base64url, a JWS that is not three parts, a header or payload that is not a JSON object, or a disclosure that is not a JSON array of two or three elements starting with a string salt (and, when three, a string claim name) |
| `unsupported_algorithm` | the header `alg` is neither `RS256` nor `ES256`, the header carries `crit`, or `_sd_alg` is present and is not `sha-256` |
| `unknown_key` | section 3 picks no published key for this credential |
| `bad_signature` | the issuer signature does not verify |
| `invalid_disclosure` | resolving the credential breaks one of the rules in section 2 |
| `missing_claim` | the resolved credential lacks a string `iss`, an integer `iat`, an integer `exp`, a name (`upn`, else `preferred_username`, else `sub`), or a `cnf` object holding a `jwk` object |
| `invalid_issuer` | `iss` is not `mp.jwt.verify.issuer` |
| `expired` | `exp` is at or before `wallet.instant` |
| `insufficient` | the policy cannot be satisfied from this credential |
| `presented` | a presentation was released |

## 5. Disclosure policy

The verifier's policy is a JSON object with `required`, a list of claim paths that must be visible,
and `alternatives`, a list of groups where at least one claim path per group must be visible. The
policy is satisfiable when every required path and at least one path in every group is present in
the resolved credential; otherwise the credential is `insufficient` and we report `missing`, the
required paths that are absent together with every path of every group that has no path present.

Releasing a claim path means releasing the disclosures that stand between it and the payload root:
a nested member stays invisible unless every enclosing disclosure travels with it. A path that
resolves to an array additionally needs the disclosures for that array's own hidden elements, since
a partial list would misrepresent it.

Data minimisation is contractual, so the wallet releases **the smallest number of disclosures** that
satisfies the policy. Groups interact, and a group's cheapest option in isolation is often not the
cheapest overall, so the released set is the smallest over all ways of choosing one path per group.
When several choices tie on size, take the one that picks the earliest listed path in the first
group, then the earliest in the second, and so on.

## 6. Released presentation

A presentation is the issuer-signed JWT, then the released disclosures each followed by `~`, then
the key binding JWT:

```
<Issuer-signed JWT>~<released Disclosure>~ ... ~<Key Binding JWT>
```

Released disclosures are ordered by ascending UTF-8 byte order of their base64url text, so a run is
reproducible. The key binding JWT is signed with the holder key at `wallet.holder.key` (a private
EC `P-256` JWK) using `ES256`, its header carries `typ` of `kb+jwt`, and its payload carries `aud`
(`wallet.audience`), `nonce` (`wallet.nonce`), `iat` (`wallet.instant`) and `sd_hash`. `sd_hash` is
base64url of `SHA-256` over the US-ASCII bytes of everything in the presentation up to and including
the `~` that precedes the key binding JWT.

Presentations are written one per released credential to `presentations/<credential id>.sdjwt`
under the output directory, on a single line, and nothing else is written there. Collection expects
that directory to exist after every run, so it is always created, empty when the run released
nothing.

## 7. Run report

`report.json` under the output directory records the run as canonical JSON: object members sorted by
name in ascending UTF-8 byte order, no insignificant whitespace, UTF-8 with only the escapes JSON
requires. Its members are `jwks_uri` (the configured location), `keys` (the usable published keys as
`kid` and `thumbprint`, ordered by `kid`), and `credentials`, one entry per credential file ordered
by identifier.

Every entry carries `id` and `status`. A `presented` entry also carries `alg` and `kid` of the
verifying key, `name` (the MicroProfile `JsonWebToken` principal name), `groups` (the resolved
`groups` claim, or an empty list), `disclosed` (the claim paths of the released disclosures) and
`sd_hash`. An `insufficient` entry also carries `missing`. Lists of claim paths, group names and
missing paths are in ascending UTF-8 byte order.

`disclosed` has one claim path for every disclosure that actually travels, not one per path the
policy named. A nested claim therefore contributes the path of each enclosing disclosure it had to
bring along as well as its own, and a released array contributes an `[index]` path for every element
disclosure it carries.

Retrieving the key set is the only thing that stops a run: the broker then exits non-zero and writes
no report. Everything else is reported per credential and the run exits zero.

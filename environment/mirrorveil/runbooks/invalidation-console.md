# Invalidation and policy activation

Administrative control-plane and policy-activation standard for the edge service. Operators confirm via HTTP status/bodies, later cache state, and `varnishadm vcl.list`.

## Required success responses

These bodies are literal plain text (no HTML error page, no trailing commentary):

| Method | Success status | Exact body |
| --- | --- | --- |
| `PURGE` | `200` | `purged` |
| `BAN` | `202` | `ban queued` |

Unauthorized or incomplete control requests (wrong/missing `X-Mirror-Control`, non-loopback client, or unsupported Host) return `405 Method Not Allowed` with `X-Edge-State: SYNTH` and must leave cache and active VCL unchanged.

Do not use `405` for a bad ban class. When control auth succeeds but `X-Ban-Class` is missing or not one of `stable`, `candidate`, `metadata`, `large`, return `400 Bad Request` with `X-Edge-State: SYNTH` and add no ban.

## Control plane

Administrative methods are accepted only when all of the following hold:

- the client is on the loopback ACL
- header `X-Mirror-Control` exactly matches the `CONTROL_MARKER` value in `/srv/mirrorveil/policy/control.conf` (header name is `CONTROL_HEADER` in that file)
- Host canonicalizes to a supported host

Loopback alone is not enough. A wrong or missing `X-Mirror-Control` is `405`, not a successful purge/ban.

`/srv/mirrorveil/bin/cache-control` wraps control traffic and origin lifecycle:

```text
cache-control origin-down primary|secondary
cache-control origin-up primary|secondary
cache-control purge HOST URL
cache-control ban-class HOST CLASS
```

## PURGE

`PURGE` applies to the canonical host and normalized URL only. Before hashing/purging, apply the same host lowercasing/port-strip, query sorting, trailing-`?` trim, and Accept-Encoding reduction used for ordinary GET storage keys — otherwise the purge hits a different object than the public cache. Success is status `200` with body exactly:

```text
purged
```

The next eligible request for that key is a miss. Other URLs, query values, encodings, or hosts stay reusable — including the same URL on the other supported host.

## Class BAN

`BAN` requires `X-Ban-Class` equal to one of `stable`, `candidate`, `metadata`, `large`. Those tokens are the origin `X-Artifact-Class` values. A successful ban returns status `202` with body exactly:

```text
ban queued
```

The ban must invalidate objects for that class on the Host that received the BAN only. It must not invalidate the other supported host even when class and URL match. Class must not be inferred from URL path segments alone.

Missing or unsupported `X-Ban-Class` returns `400 Bad Request` with `X-Edge-State: SYNTH` and adds no ban.

Administrative requests never reach an origin and never populate storage. Control and ban headers are not forwarded on ordinary backend fetches.

## VCL reload

`reload-cache-policy` validates the installed VCL with the real Varnish compiler first. Compile failure returns nonzero, reports the compiler error, and leaves the active VCL unchanged. Do not start or activate a generation that failed to compile.

The activated label is exactly:

```text
mv_<16 lowercase hex chars>
```

where those sixteen characters are the first sixteen hex digits of one SHA-256 digest over the VCL source set.

### Source set

Include only files matching `/srv/mirrorveil/vcl/*.vcl` (six files today). Sort by the relative path string `vcl/<filename>` using ordinary byte/lexical order (examples: `vcl/backends.vcl` before `vcl/entry.vcl`). Do not include policy, nginx, bin, runbooks, or any non-`*.vcl` file.

### Byte framing (normative)

Maintain a single SHA-256 hasher. For each file in the sorted order above, feed these bytes in order, with no separators between files beyond this framing:

1. relative path as UTF-8: `vcl/<filename>`
2. one NUL byte (`0x00`)
3. decimal ASCII byte length of the file contents, no `+` sign, no leading zeros (use `0` only when the file is empty)
4. one NUL byte (`0x00`)
5. the raw file bytes unchanged

Worked single-file fragment: if `vcl/entry.vcl` is 822 bytes, feed exactly:

```text
vcl/entry.vcl <NUL> 822 <NUL> <822 raw bytes>
```

Do that for every `*.vcl` file, still on the same hasher. Then take `hexdigest[:16]` and prefix `mv_`. Any other framing (path-only hash, raw concatenation without NULs/lengths, sorting by basename alone, hashing `entry.vcl` without the `vcl/` prefix, or hashing after pretty-printing) produces a wrong label and fails activation checks.

Normative reference implementation (identical contract to the verifier). Operators may call `/srv/mirrorveil/bin/compute-vcl-label`, which prints the full `mv_…` label:

```python
import hashlib
from pathlib import Path
root = Path("/srv/mirrorveil/vcl")
h = hashlib.sha256()
for path in sorted(root.glob("*.vcl")):
    rel = f"vcl/{path.name}"
    data = path.read_bytes()
    h.update(rel.encode("utf-8"))
    h.update(b"\0")
    h.update(str(len(data)).encode("ascii"))
    h.update(b"\0")
    h.update(data)
label = "mv_" + h.hexdigest()[:16]
```

### Activation rules

An identical already-loaded generation is reused: a second `reload-cache-policy` for the same digest must succeed (exit 0) and keep that label active — do not fail on varnishadm duplicate-name load errors. After activation, discard only inactive labels that begin with `mv_` and are not the active label. Do not discard the boot label before the first successful task activation, and do not discard foreign labels. `start-cache-stack` must leave this exact content-addressed `mv_` generation active after start or restart (not a temporary boot label). `/srv/mirrorveil/bin/compute-vcl-label` is the authoritative label string for the current tree.

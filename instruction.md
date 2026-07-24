Our inbox accepts authenticated JWE messages (ECDH-1PU authcrypt, the DIDComm shape) through a
third-party JOSE stack that security wants gone. `/app/unsealer` is a Maven module with a stub
`Main`; finish it so `mvn -f /app/unsealer/pom.xml package` builds `/app/unsealer/target/jwe-unsealer.jar`,
run as

```
java -jar /app/unsealer/target/jwe-unsealer.jar --keys <keys> --senders <senders> --messages <msgs> --out <report> --digest <digest>
```

No third-party JOSE, JWT or crypto code may reach that jar: JDK crypto and a JSON parser only.
`<keys>` is a JWK Set of our recipient private P-256 keys; `<senders>` is `{"senders": {"<skid>":
"<jwks_uri>"}}`; `<msgs>` holds one JWE per non-empty line, each compact (five segments) or a
flattened or general JSON object.

Only `alg` `ECDH-1PU+A256KW` and `enc` `A256GCM` over P-256 are supported. Read `alg`, `enc`, `epk`,
`apu`, `apv` and the sender key id `skid` from the protected header; each recipient carries its own
`kid` and `encrypted_key`. ECDH-1PU agrees `Z = Ze || Zs`: `Ze` against the ephemeral `epk`, `Zs`
against the sender's static key, both from the recipient private key. Fetch the sender's static key
from the `skid` entry of `<senders>` (its `jwks_uri`, read at most once each and cached, the key
whose `kid` is the `skid`). Derive the key-encryption key with the Concat KDF and unwrap the content
key (RFC 3394), then decrypt with AES-GCM whose AAD is the ASCII protected header, or, when a JWE
`aad` is present, the protected header, a `.`, and the `aad`.

```
KEK = SHA-256( 00000001 | Z | len(algID) algID | len(apu) apu | len(apv) apv | 00000100 )
```

`algID` is `ECDH-1PU+A256KW` as ASCII; `apu`/`apv` are the base64url-decoded header bytes, empty when
absent; every length and the trailing key length (256) is a 32-bit big-endian integer; `KEK` is the
32-byte digest.

Report each message by index in `<report>`:

```json
{"results": [
  {"index": 0, "status": "unsealed", "recipient_kid": "k1", "sender_kid": "s1",
   "sender_thumbprint": "<RFC 7638>", "name": "...", "sub": "...", "groups": ["..."]},
  {"index": 1, "status": "unknown_sender", "recipient_kid": "k1"},
  {"index": 2, "status": "unsupported_algorithm"}]}
```

| status | raised when |
|---|---|
| `malformed` | not a JWE in any serialization, the protected header is not a JSON object, or a required member is missing |
| `unsupported_algorithm` | `alg` is not `ECDH-1PU+A256KW`, `enc` is not `A256GCM`, or `epk` is not a P-256 public key |
| `no_recipient` | no held key matches a recipient `kid` |
| `unknown_sender` | no `skid`, it is absent from the registry, or its key set has no matching P-256 key |
| `bad_key` | the derived key does not unwrap the content key |
| `bad_tag` | the content does not authenticate under AES-GCM |
| `unsealed` | the message decrypts |

`recipient_kid` appears once a held key matches; `sender_kid` and the resolved key's `sender_thumbprint`
once the sender resolves; `name` (`upn`, else `preferred_username`, else `sub`, else null), `sub`
(else null) and `groups` (byte-sorted) only on `unsealed`. The report is canonical JSON: object keys
sorted by UTF-8 byte order, compact separators, no other whitespace. To `<digest>` write the
lowercase-hex SHA-256 over, for each message in order, its status text then `\n`, and for `unsealed`
messages the recovered plaintext bytes then `\n`.

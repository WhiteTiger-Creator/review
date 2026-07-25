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

A message is structurally invalid when it is neither five dot-separated segments nor a JSON object;
when `protected`, `iv`, `ciphertext`, `tag` or any recipient's `encrypted_key` is absent; when the
protected header does not base64url-decode to a JSON object; or when **any** segment or base64url
member (`protected`, `encrypted_key`, `iv`, `ciphertext`, `tag`, `aad`) contains characters outside
the base64url alphabet or otherwise fails to decode.

The supported algorithms are `alg` `ECDH-1PU+A256KW` and `enc` `A256GCM` over P-256, and `DEF` is the
only permitted `zip`. `alg`, `enc`, `epk`, `apu`, `apv`, `zip` and the sender key id `skid` are the
protected header's; a recipient's `kid` and `encrypted_key` are its own. ECDH-1PU agrees
`Z = Ze || Zs`: `Ze` against the ephemeral `epk`, `Zs` against the sender's static key, both from the
recipient private key. The sender's static key is the one whose `kid` equals the `skid` in the JWK
Set at the `jwks_uri` that `<senders>` maps that `skid` to, and each `jwks_uri` is read at most once
per run. The content key is the RFC 3394 unwrap of `encrypted_key` under the key-encryption key
below; the plaintext is the AES-GCM decryption of `ciphertext` under that content key with the
message's `iv` and `tag`, whose AAD is the ASCII protected header, or, when a JWE `aad` is present,
the protected header, a `.`, and the `aad`. Under `zip` `DEF` that plaintext is raw DEFLATE
(RFC 1951, no zlib or gzip wrapper) and the message is what it inflates to.

```
KEK = SHA-256( 00000001 | Z | len(algID) algID | len(apu) apu | len(apv) apv | 00000100 | len(tag) tag )
```

`algID` is `ECDH-1PU+A256KW` as ASCII; `apu`/`apv` are the base64url-decoded header bytes, empty when
absent; `tag` is the message's own authentication tag, which key wrapping binds into the derived key;
every length and the key length (256) is a 32-bit big-endian integer; `KEK` is the 32-byte digest.

Report each message by index in `<report>`:

```json
{"results": [
  {"index": 0, "status": "unsealed", "recipient_kid": "k1", "sender_kid": "s1",
   "sender_thumbprint": "<RFC 7638>", "name": "...", "sub": "...", "groups": ["..."]},
  {"index": 1, "status": "unknown_sender", "recipient_kid": "k1"},
  {"index": 2, "status": "unsupported_algorithm"}]}
```

Each message has exactly one status, and a message meeting the conditions of more than one row below
takes the status of the earliest such row.

| status | raised when |
|---|---|
| `malformed` | the message is structurally invalid |
| `unsupported_algorithm` | `alg` is not `ECDH-1PU+A256KW`, `enc` is not `A256GCM`, `zip` is present and is not `DEF`, or `epk` is not a P-256 public key |
| `no_recipient` | no held key matches a recipient `kid` |
| `unknown_sender` | no `skid`, it is absent from the registry, or its key set has no matching P-256 key |
| `bad_key` | the derived key does not unwrap the content key |
| `bad_tag` | the content does not authenticate under AES-GCM |
| `unsealed` | the message decrypts |

A result carries `index` and `status`, and nothing further for `malformed`, `unsupported_algorithm`
and `no_recipient`. It also carries `recipient_kid` where a held key matched the message, `sender_kid`
and the resolved key's `sender_thumbprint` where the sender resolved, and `name` (`upn`, else
`preferred_username`, else `sub`, else null), `sub` (else null) and `groups` (byte-sorted) where the
status is `unsealed`. Every object in
the report, including each result, is canonical JSON: keys sorted by UTF-8 byte order, compact
separators, no other whitespace. To `<digest>` write the lowercase-hex SHA-256 over, for each message
in order, its status text then `\n`, and for `unsealed` messages the recovered plaintext bytes then
`\n`.

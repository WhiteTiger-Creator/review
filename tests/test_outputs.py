"""Behavioural checks for the Acme inbox JWE unsealer.

Every fixture is minted fresh: new recipient, sender and ephemeral keys, new plaintexts, a new local
registry on a new port. The expected report and transcript digest are recomputed here from the same
public specifications the tool must follow, so a stored answer cannot pass.
"""

import hashlib
import json
import os
import time
import urllib.request
import zipfile

import jose_ref as ref

GITHUB_JWKS = (
    "https://raw.githubusercontent.com/eclipse/microprofile-jwt-auth/"
    "d729a3f276a530ce5c471f23dbb2d253b891eb8f/tck/src/test/resources/rs256es256.jwk"
)
JOSE_LIBRARY_PACKAGES = (
    "org/jose4j/",
    "com/nimbusds/",
    "io/jsonwebtoken/",
    "com/auth0/",
    "org/bouncycastle/",
    "org/apache/commons/codec/",
    "com/google/crypto/",
)


class Run:
    """One unsealer invocation: what the tool produced and what the reference expected."""

    def __init__(self, process, report_bytes, report, digest, exp_report, exp_digest):
        self.process = process
        self.report_bytes = report_bytes
        self.report = report
        self.digest = digest
        self.exp_report = exp_report
        self.exp_digest = exp_digest

    def statuses(self):
        return ref.statuses(self.report)


def run(tmp_path, held, senders, items):
    """Seals the items, runs the jar over them, and returns the actual and expected outputs."""
    messages, expected_report, expected_digest = ref.assemble(items)
    process, report_bytes, report, digest = ref.run_unsealer(tmp_path, held, senders, messages)
    return Run(process, report_bytes, report, digest, expected_report, expected_digest)


def test_build_produces_the_runnable_jar():
    """The module builds to the executable jar the inbox ships."""
    assert os.path.isfile(ref.JAR), "expected the packaged jar at " + ref.JAR


def test_no_third_party_jose_code_is_shipped():
    """Neither the jar nor its declared classpath carries a third-party JOSE, JWT or crypto library."""
    with zipfile.ZipFile(ref.JAR) as jar:
        entries = jar.namelist()
        manifest = jar.read("META-INF/MANIFEST.MF").decode("utf-8", "replace")
    bundled = [name for name in entries if name.startswith(JOSE_LIBRARY_PACKAGES)]
    assert bundled == [], "third-party JOSE code in the jar: " + ", ".join(sorted(bundled)[:5])
    assert "Class-Path:" not in manifest, "the jar pulls code in from outside its own classpath"


def test_all_three_serializations_unseal_byte_exact(tmp_path):
    """Compact, flattened and general ECDH-1PU messages all unseal, with a byte-exact report and digest.

    A recipient-only ECDH-ES key agreement, a wrong Concat KDF algorithm id, or the wrong AAD would
    each derive a different key or tag and fail every one of these, so passing pins the full pipeline.
    """
    bob, carol, alice = ref.EcKey("bob-1"), ref.EcKey("carol-1"), ref.EcKey("alice-static")
    first, second, third = ref.claims(), ref.claims(preferred_username="al"), ref.claims(groups=None)
    with ref.Registry([alice.public_jwk()]) as registry:
        senders = {"alice-static": registry.url}
        items = [
            (ref.seal("compact", [bob], alice, ref.canonical(first), apu=b"Alice", apv=b"Bob"),
             *ref.unsealed(bob, alice, first)),
            (ref.seal("flattened", [bob], alice, ref.canonical(second), aad=b"delivery-context"),
             *ref.unsealed(bob, alice, second)),
            (ref.seal("general", [carol, bob], alice, ref.canonical(third)),
             *ref.unsealed(bob, alice, third)),
        ]
        result = run(tmp_path, [bob.private_jwk()], senders, items)

    assert result.process.returncode == 0, result.process.stderr
    assert result.statuses() == ["unsealed", "unsealed", "unsealed"]
    assert result.report_bytes == ref.canonical(result.exp_report)
    assert result.digest == result.exp_digest
    assert [r.get("recipient_kid") for r in result.report["results"]] == ["bob-1", "bob-1", "bob-1"]


def test_principal_name_falls_back_through_the_claims(tmp_path):
    """The reported name is upn, then preferred_username, then sub, and groups are byte-sorted."""
    bob, alice = ref.EcKey("bob-1"), ref.EcKey("alice-static")
    both = ref.claims(preferred_username="pref", groups=["ops", "admin", "sre"])
    only_pref = ref.claims(upn=None, preferred_username="pref")
    only_sub = ref.claims(upn=None, groups=None)
    none_at_all = ref.claims(upn=None, sub=None)
    with ref.Registry([alice.public_jwk()]) as registry:
        senders = {"alice-static": registry.url}
        items = [(ref.seal("compact", [bob], alice, ref.canonical(p)), *ref.unsealed(bob, alice, p))
                 for p in (both, only_pref, only_sub, none_at_all)]
        result = run(tmp_path, [bob.private_jwk()], senders, items)

    assert result.process.returncode == 0, result.process.stderr
    assert result.report_bytes == ref.canonical(result.exp_report)
    names = [r["name"] for r in result.report["results"]]
    assert names == ["alice@acme.example", "pref", "24400320", None]
    assert result.report["results"][0]["groups"] == ["admin", "ops", "sre"]
    assert result.report["results"][3]["sub"] is None


def test_algorithm_and_ephemeral_key_policy(tmp_path):
    """A non-1PU alg, a non-GCM enc, and a non-P-256 ephemeral key are all unsupported_algorithm."""
    bob, alice = ref.EcKey("bob-1"), ref.EcKey("alice-static")
    payload = ref.canonical(ref.claims())
    with ref.Registry([alice.public_jwk()]) as registry:
        senders = {"alice-static": registry.url}
        items = [
            (ref.seal("compact", [bob], alice, payload, alg="ECDH-ES+A256KW"),
             *ref.rejected("unsupported_algorithm")),
            (ref.seal("compact", [bob], alice, payload, enc="A128GCM"),
             *ref.rejected("unsupported_algorithm")),
            (ref.seal("compact", [bob], alice, payload, bad_epk_crv=True),
             *ref.rejected("unsupported_algorithm")),
        ]
        result = run(tmp_path, [bob.private_jwk()], senders, items)

    assert result.process.returncode == 0, result.process.stderr
    assert result.statuses() == ["unsupported_algorithm"] * 3
    assert result.report_bytes == ref.canonical(result.exp_report)


def test_recipient_is_selected_from_the_held_keys(tmp_path):
    """A message is no_recipient when no held key matches, and the held recipient is found among several."""
    bob, carol, dave = ref.EcKey("bob-1"), ref.EcKey("carol-1"), ref.EcKey("dave-1")
    alice = ref.EcKey("alice-static")
    payload = ref.claims()
    with ref.Registry([alice.public_jwk()]) as registry:
        senders = {"alice-static": registry.url}
        items = [
            (ref.seal("compact", [dave], alice, ref.canonical(payload)), *ref.rejected("no_recipient")),
            (ref.seal("general", [dave, carol, bob], alice, ref.canonical(payload)),
             *ref.unsealed(bob, alice, payload)),
        ]
        result = run(tmp_path, [bob.private_jwk()], senders, items)

    assert result.process.returncode == 0, result.process.stderr
    assert result.statuses() == ["no_recipient", "unsealed"]
    assert "recipient_kid" not in result.report["results"][0]
    assert result.report["results"][1]["recipient_kid"] == "bob-1"
    assert result.report_bytes == ref.canonical(result.exp_report)


def test_sender_must_be_resolvable_before_decryption(tmp_path):
    """No skid, an unregistered skid, and a skid absent from the fetched key set are all unknown_sender."""
    bob, alice, other = ref.EcKey("bob-1"), ref.EcKey("alice-static"), ref.EcKey("someone-else")
    payload = ref.canonical(ref.claims())
    with ref.Registry([other.public_jwk()]) as registry:  # serves a set that lacks 'alice-static'
        senders = {"alice-static": registry.url}
        items = [
            (ref.seal("compact", [bob], alice, payload, drop_skid=True),
             *ref.rejected("unknown_sender", bob)),
            (ref.seal("compact", [bob], alice, payload, skid="ghost"),
             *ref.rejected("unknown_sender", bob)),
            (ref.seal("compact", [bob], alice, payload, skid="alice-static"),
             *ref.rejected("unknown_sender", bob)),
        ]
        result = run(tmp_path, [bob.private_jwk()], senders, items)

    assert result.process.returncode == 0, result.process.stderr
    assert result.statuses() == ["unknown_sender"] * 3
    assert all(r["recipient_kid"] == "bob-1" for r in result.report["results"])
    assert all("sender_kid" not in r for r in result.report["results"])
    assert result.report_bytes == ref.canonical(result.exp_report)


def test_wrong_published_sender_key_fails_the_key_unwrap(tmp_path):
    """When the registry publishes a different key than the one that sealed the message, it is bad_key.

    The sender's static key enters the key agreement as the second ECDH input, so a mismatched
    published key derives the wrong key-encryption key and the RFC 3394 unwrap integrity check fails.
    """
    bob, alice, impostor = ref.EcKey("bob-1"), ref.EcKey("alice-static"), ref.EcKey("alice-static")
    payload = ref.canonical(ref.claims())
    with ref.Registry([impostor.public_jwk()]) as registry:  # same kid, different key than 'alice'
        senders = {"alice-static": registry.url}
        items = [(ref.seal("compact", [bob], alice, payload), *ref.rejected("bad_key", bob, impostor))]
        result = run(tmp_path, [bob.private_jwk()], senders, items)

    assert result.process.returncode == 0, result.process.stderr
    assert result.statuses() == ["bad_key"]
    assert result.report["results"][0]["sender_thumbprint"] == impostor.thumbprint()
    assert result.report_bytes == ref.canonical(result.exp_report)


def test_tampered_ciphertext_and_corrupt_key_are_distinguished(tmp_path):
    """A flipped tag is bad_tag while a corrupted wrapped key is bad_key: the two failures do not merge."""
    bob, alice = ref.EcKey("bob-1"), ref.EcKey("alice-static")
    payload = ref.canonical(ref.claims())
    with ref.Registry([alice.public_jwk()]) as registry:
        senders = {"alice-static": registry.url}
        items = [
            (ref.seal("compact", [bob], alice, payload, tamper_tag=True),
             *ref.rejected("bad_tag", bob, alice)),
            (ref.seal("compact", [bob], alice, payload, corrupt_ek=True),
             *ref.rejected("bad_key", bob, alice)),
        ]
        result = run(tmp_path, [bob.private_jwk()], senders, items)

    assert result.process.returncode == 0, result.process.stderr
    assert result.statuses() == ["bad_tag", "bad_key"]
    assert result.report_bytes == ref.canonical(result.exp_report)


def test_additional_authenticated_data_is_bound_into_the_tag(tmp_path):
    """A message carrying a JWE aad member unseals only when that aad is folded into the GCM AAD."""
    bob, alice = ref.EcKey("bob-1"), ref.EcKey("alice-static")
    payload = ref.claims(groups=["ops"])
    with ref.Registry([alice.public_jwk()]) as registry:
        senders = {"alice-static": registry.url}
        items = [(ref.seal("flattened", [bob], alice, ref.canonical(payload), aad=b"binding-context"),
                  *ref.unsealed(bob, alice, payload))]
        result = run(tmp_path, [bob.private_jwk()], senders, items)

    assert result.process.returncode == 0, result.process.stderr
    assert result.statuses() == ["unsealed"]
    assert result.report_bytes == ref.canonical(result.exp_report)
    assert result.digest == result.exp_digest


def test_structurally_broken_messages_are_malformed(tmp_path):
    """Messages that are not a JWE in any serialization never reach key resolution."""
    bob, alice = ref.EcKey("bob-1"), ref.EcKey("alice-static")
    good = ref.seal("compact", [bob], alice, ref.canonical(ref.claims()))
    header = good.split(".")[0]
    with ref.Registry([alice.public_jwk()]) as registry:
        senders = {"alice-static": registry.url}
        items = [
            ("aa.bb.cc", *ref.rejected("malformed")),                        # not five segments
            (header + ".!!bad!!." + header + "." + header + "." + header, *ref.rejected("malformed")),
            (ref.b64u(b"[1,2,3]") + "." + header + "." + header + "." + header + "." + header,
             *ref.rejected("malformed")),                                    # protected is not an object
            ('{"protected":"' + header + '","iv":"AAAA"}', *ref.rejected("malformed")),  # missing members
        ]
        result = run(tmp_path, [bob.private_jwk()], senders, items)

    assert result.process.returncode == 0, result.process.stderr
    assert result.statuses() == ["malformed"] * 4
    assert result.report_bytes == ref.canonical(result.exp_report)


def test_registry_is_fetched_at_most_once_per_uri(tmp_path):
    """Several messages naming the same sender resolve through a single registry fetch that is cached."""
    bob, alice = ref.EcKey("bob-1"), ref.EcKey("alice-static")
    with ref.Registry([alice.public_jwk()]) as registry:
        senders = {"alice-static": registry.url}
        payloads = [ref.claims(sub=str(n)) for n in range(4)]
        items = [(ref.seal("compact", [bob], alice, ref.canonical(p)), *ref.unsealed(bob, alice, p))
                 for p in payloads]
        result = run(tmp_path, [bob.private_jwk()], senders, items)
        fetches = registry.count

    assert result.process.returncode == 0, result.process.stderr
    assert result.statuses() == ["unsealed"] * 4
    assert fetches == 1, f"the registry key set was fetched {fetches} times, expected one cached read"
    assert result.report_bytes == ref.canonical(result.exp_report)


def test_transcript_digest_covers_the_recovered_plaintext(tmp_path):
    """The digest is over the statuses and the recovered plaintext bytes, not over the report file."""
    bob, alice = ref.EcKey("bob-1"), ref.EcKey("alice-static")
    payload = ref.claims(groups=["a", "b"])
    with ref.Registry([alice.public_jwk()]) as registry:
        senders = {"alice-static": registry.url}
        items = [
            (ref.seal("compact", [bob], alice, ref.canonical(payload)), *ref.unsealed(bob, alice, payload)),
            (ref.seal("compact", [bob], alice, ref.canonical(payload), tamper_tag=True),
             *ref.rejected("bad_tag", bob, alice)),
        ]
        result = run(tmp_path, [bob.private_jwk()], senders, items)

    assert result.process.returncode == 0, result.process.stderr
    assert result.digest == result.exp_digest
    expected = hashlib.sha256(b"unsealed\n" + ref.canonical(payload) + b"\n" + b"bad_tag\n").hexdigest()
    assert result.digest == expected
    assert result.digest != hashlib.sha256(result.report_bytes).hexdigest(), \
        "the digest must not be a hash of the report"


def test_live_sender_key_is_resolved_over_the_network(tmp_path):
    """Against a real published key set the tool fetches the sender's static key and thumbprints it.

    The message is sealed locally with a different sender key, so the correct outcome once the real
    key is agreed against is bad_key; the reported RFC 7638 thumbprint proves the live resolution.
    """
    published = _fetch(GITHUB_JWKS)
    ec_key = next(k for k in published["keys"] if k.get("kty") == "EC" and k.get("crv") == "P-256")
    expected_thumbprint = ref.thumbprint(ec_key)

    bob, local_sender = ref.EcKey("bob-1"), ref.EcKey("eckey")
    payload = ref.canonical(ref.claims())
    message = ref.seal("general", [bob], local_sender, payload, skid="eckey")
    senders = {"eckey": GITHUB_JWKS}
    process, _, report, digest = ref.run_unsealer(tmp_path, [bob.private_jwk()], senders, [message])

    assert process.returncode == 0, process.stderr
    result = report["results"][0]
    assert result["sender_kid"] == "eckey"
    assert result["sender_thumbprint"] == expected_thumbprint, "wrong RFC 7638 thumbprint for the live key"
    assert result["status"] == "bad_key"
    assert digest == hashlib.sha256(b"bad_key\n").hexdigest()


def _fetch(url, attempts=4):
    failure = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError) as error:
            # URLError, HTTPError, timeouts and refused connections are all OSError; a truncated or
            # non-JSON body raises ValueError. Every one of them is worth another attempt.
            failure = error
            time.sleep(1.5 * (attempt + 1))
    raise AssertionError(f"could not reach {url}: {failure}")

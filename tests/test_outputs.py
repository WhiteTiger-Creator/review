"""Behavioural checks for the Acme wallet presentation broker.

Every credential a test uses is minted here, with fresh keys and a fresh issuer, and every expected
report, claim path, digest and presentation is recomputed from the profile by an independent
implementation. Nothing in this file is compared against a stored answer, so a broker that hardcodes
outputs cannot pass.
"""

import collections
import json
import os
import zipfile

import pytest
import sdjwt_ref as ref

Run = collections.namedtuple("Run", "process report out expected presentations")

JOSE_LIBRARY_PACKAGES = (
    "org/jose4j/",
    "com/nimbusds/",
    "io/jsonwebtoken/",
    "com/auth0/",
    "org/bouncycastle/",
    "com/google/crypto/",
    "org/apache/commons/codec/",
)

SD_PATHS = [
    "given_name",
    "family_name",
    "contact",
    "contact.person",
    "contact.person.email",
    "contact.person.im",
    "work",
    "work.site",
    "work.site.phone",
    "work.site.desk",
    "residence",
    "residence.address",
    "residence.address.country",
    "residence.address.geo",
    "residence.address.geo.lat",
    "residence.address.geo.lon",
    "nationalities[0]",
    "nationalities[1]",
    "nationalities[2]",
]

POLICY = {
    "required": ["given_name", "nationalities"],
    "alternatives": [
        ["contact.person.email", "residence.address.geo.lat"],
        ["work.site.phone", "residence.address.geo.lon"],
    ],
}


@pytest.fixture(scope="module")
def keys():
    """One issuer key of each shape plus the holder key the wallet signs with."""
    return {
        "ec": ref.SigningKey("issuer-ec", "EC", alg="ES256", use="sig"),
        "rsa": ref.SigningKey("issuer-rsa", "RSA", alg="RS256", use="sig"),
        "holder": ref.SigningKey("acme-wallet-1", "EC"),
    }


def claims(holder, **overrides):
    """A MicroProfile-shaped claim set for one credential holder."""
    base = {
        "iss": ref.DEFAULT_CONFIG["issuer"],
        "iat": 1769000000,
        "exp": 1780000000,
        "jti": "urn:acme:cred:test",
        "upn": "mira.holt@acme.example",
        "sub": "0d1f8c4a",
        "groups": ["staff", "engineering", "on-call"],
        "given_name": "Mira",
        "family_name": "Holt",
        "contact": {"person": {"email": "mira.holt@acme.example", "im": "mira#4411"}},
        "work": {"site": {"phone": "+31-20-555-0111", "desk": "B2-14"}},
        "residence": {"address": {"country": "NL", "geo": {"lat": "52.3702", "lon": "4.8952"}}},
        "nationalities": ["NL", "DE", "FR"],
        "cnf": {"jwk": holder.jwk()},
    }
    base.update(overrides)
    return {name: value for name, value in base.items() if value is not None}


def drive(tmp_path, credentials, policy, published, holder, config=None):
    """Run the broker over a batch served by a local issuer, next to what the profile expects."""
    config = config or ref.DEFAULT_CONFIG
    jwks = {"keys": published}
    with ref.JwksServer(jwks) as server:
        process, report, out = ref.run_broker(tmp_path, credentials, policy, server.url, holder, config)
        expected, presentations = ref.expected_report(credentials, jwks, server.url, policy, config)
    return Run(process, report, out, ref.canonical(expected), presentations)


def entries(report):
    """The credential entries of a report, keyed by identifier."""
    return {entry["id"]: entry for entry in json.loads(report)["credentials"]}


def test_build_produces_the_runnable_jar():
    """The broker module packages to the executable jar the wallet ships."""
    assert os.path.isfile(ref.JAR), "expected the packaged jar at " + ref.JAR


def test_broker_uses_no_third_party_jose_code():
    """No third-party JOSE, JWT or crypto library is bundled into the broker jar."""
    with zipfile.ZipFile(ref.JAR) as archive:
        names = archive.namelist()
    bundled = [name for name in names if name.startswith(JOSE_LIBRARY_PACKAGES)]
    assert bundled == [], "third-party JOSE code in the jar: " + ", ".join(sorted(bundled)[:5])


def test_report_matches_the_profile_for_a_fresh_batch(tmp_path, keys):
    """A mixed batch produces the canonical report the profile describes, byte for byte."""
    holder = keys["holder"]
    batch = {
        "atlas": ref.issue(keys["ec"], claims(holder), SD_PATHS, decoys=2, seed=1).issuance(),
        "bergen": ref.issue(
            keys["rsa"],
            claims(holder, upn=None, preferred_username="tomás.nakamura", given_name="Tomas"),
            SD_PATHS + ["preferred_username"],
            decoys=3,
            seed=2,
            spacing="compact",
        ).issuance(),
        "cove": ref.issue(
            keys["ec"],
            claims(holder, work=None, contact={"person": {"im": "rune#77"}}),
            ["given_name", "residence", "residence.address"],
            seed=3,
        ).issuance(),
        "delta": ref.issue(keys["ec"], claims(holder, exp=1700000000), SD_PATHS, seed=4).issuance(),
    }
    published = [keys["ec"].jwk(), keys["rsa"].jwk()]
    run = drive(tmp_path, batch, POLICY, published, holder)

    assert run.process.returncode == 0, run.process.stderr
    assert run.report is not None, "the broker wrote no report"
    assert run.report == run.expected, (
        f"report differs from the profile\nexpected: {run.expected.decode('utf-8')}"
        f"\nactual:   {run.report.decode('utf-8')}"
    )
    assert set(os.listdir(os.path.join(run.out, "presentations"))) == {
        name + ".sdjwt" for name in run.presentations
    }


def test_acceptance_ladder_reports_the_first_failing_check(tmp_path, keys):
    """Every rung of the ladder is reached by the credential that trips it, and no earlier one."""
    holder = keys["holder"]
    stranger = ref.SigningKey("retired-2024", "EC")
    good = ref.issue(keys["ec"], claims(holder), SD_PATHS, decoys=1, seed=11)
    head, body, signature = good.jwt.split(".")
    tampered = ".".join([head, body, ("B" if signature[0] != "B" else "C") + signature[1:]])
    legacy = ref.b64u(ref.canonical({"alg": "HS256", "kid": keys["ec"].kid}))
    critical = ref.issue(keys["ec"], claims(holder), SD_PATHS, seed=12, header={"crit": ["exp"]})
    other_alg = ref.issue(keys["ec"], claims(holder), SD_PATHS, seed=13, sd_alg="sha-512")

    batch = {
        "a-garbled": good.jwt + "~" + good.disclosures[0][:-2] + "*!~",
        "b-unterminated": good.issuance()[:-1],
        "c-legacy": legacy + "." + body + "." + signature + "~",
        "d-critical": critical.issuance(),
        "e-digest-alg": other_alg.issuance(),
        "f-rotated": ref.issue(stranger, claims(holder), SD_PATHS, seed=14).issuance(),
        "g-tampered": tampered + "~" + "".join(text + "~" for text in good.disclosures),
        "h-nameless": ref.issue(
            keys["rsa"], claims(holder, upn=None, sub=None), SD_PATHS, seed=15
        ).issuance(),
        "i-unbound": ref.issue(keys["ec"], claims(holder, cnf=None), SD_PATHS, seed=16).issuance(),
        "j-imposter": ref.issue(
            keys["ec"], claims(holder, iss="https://issuer.other.example"), SD_PATHS, seed=17
        ).issuance(),
        "k-lapsed": ref.issue(
            keys["ec"], claims(holder, exp=ref.DEFAULT_CONFIG["instant"]), SD_PATHS, seed=18
        ).issuance(),
        "l-released": good.issuance(),
    }
    published = [keys["ec"].jwk(), keys["rsa"].jwk()]
    run = drive(tmp_path, batch, POLICY, published, holder)

    assert run.process.returncode == 0, run.process.stderr
    found = {name: entry["status"] for name, entry in entries(run.report).items()}
    assert found == {
        "a-garbled": "malformed",
        "b-unterminated": "malformed",
        "c-legacy": "unsupported_algorithm",
        "d-critical": "unsupported_algorithm",
        "e-digest-alg": "unsupported_algorithm",
        "f-rotated": "unknown_key",
        "g-tampered": "bad_signature",
        "h-nameless": "missing_claim",
        "i-unbound": "missing_claim",
        "j-imposter": "invalid_issuer",
        "k-lapsed": "expired",
        "l-released": "presented",
    }


def test_disclosure_digests_follow_the_text_the_issuer_wrote(tmp_path, keys):
    """Digests are taken over the disclosure as received, whatever JSON layout the issuer used."""
    holder = keys["holder"]
    batch = {}
    for name, spacing in (("spaced", "spaced"), ("compact", "compact")):
        batch[name] = ref.issue(
            keys["ec"],
            claims(
                holder,
                upn=None,
                preferred_username="jürgen.möller",
                given_name="Jürgen",
            ),
            SD_PATHS + ["preferred_username"],
            decoys=2,
            seed=21,
            spacing=spacing,
        ).issuance()
    run = drive(tmp_path, batch, POLICY, [keys["ec"].jwk()], holder)

    assert run.process.returncode == 0, run.process.stderr
    found = entries(run.report)
    for name in batch:
        assert found[name]["status"] == "presented", name + " did not resolve its disclosures"
        assert found[name]["name"] == "jürgen.möller"
        assert "given_name" in found[name]["disclosed"]


def test_nested_disclosures_resolve_all_the_way_down(tmp_path, keys):
    """A claim hidden four levels deep needs every enclosing disclosure to travel with it."""
    holder = keys["holder"]
    deep = claims(
        holder,
        residence={"address": {"country": "NL", "geo": {"lat": "52.3702", "lon": "4.8952"}}},
    )
    credential = ref.issue(keys["ec"], deep, SD_PATHS, decoys=2, seed=31)
    policy = {"required": ["given_name", "residence.address.geo.lat"], "alternatives": []}
    run = drive(
        tmp_path, {"deep": credential.issuance()}, policy, [keys["ec"].jwk()], holder
    )

    assert run.process.returncode == 0, run.process.stderr
    entry = entries(run.report)["deep"]
    assert entry["status"] == "presented"
    assert entry["disclosed"] == [
        "given_name",
        "residence",
        "residence.address",
        "residence.address.geo",
        "residence.address.geo.lat",
    ]
    assert ref.read_presentation(run.out, "deep").count("~") == len(entry["disclosed"]) + 1


def test_decoy_digests_are_ignored_while_stray_disclosures_are_not(tmp_path, keys):
    """Unmatched digests are dropped, but an unused or repeated disclosure rejects the credential."""
    holder = keys["holder"]
    padded = ref.issue(keys["ec"], claims(holder), SD_PATHS, decoys=12, seed=41)
    orphaned = ref.issue(keys["ec"], claims(holder), SD_PATHS, decoys=1, seed=42)
    stray = ref.disclosure(["Xz9QpLm4Tt0aBcDeFgHiJw", "clearance", "amber"])

    twinned = ref.issue(keys["ec"], claims(holder), SD_PATHS, decoys=1, seed=43)
    payload = json.loads(ref.b64u_decode(twinned.jwt.split(".")[1]))
    repeated = payload["_sd"][0]
    payload["residence"] = {"_sd": [repeated]}
    duplicated = ref.jws(keys["ec"], payload) + "~" + "".join(t + "~" for t in twinned.disclosures)

    batch = {
        "padded": padded.issuance(),
        "orphaned": orphaned.issuance() + stray + "~",
        "duplicated": duplicated,
    }
    run = drive(tmp_path, batch, POLICY, [keys["ec"].jwk()], holder)

    assert run.process.returncode == 0, run.process.stderr
    found = entries(run.report)
    assert found["padded"]["status"] == "presented", "decoy digests must not reject a credential"
    assert found["orphaned"]["status"] == "invalid_disclosure"
    assert found["duplicated"]["status"] == "invalid_disclosure"


def test_array_elements_are_addressed_by_their_resolved_position(tmp_path, keys):
    """Array element paths count positions in the resolved list, not in the issued one."""
    holder = keys["holder"]
    paths = [path for path in SD_PATHS if not path.startswith("nationalities")]
    paths += [f"nationalities[{index}]" for index in range(4)]
    credential = ref.issue(
        keys["ec"],
        claims(holder, nationalities=["JP", "NL", "BE", "FR"]),
        paths,
        decoys=2,
        seed=51,
    )
    batch = {"shifted": credential.issuance(withheld={"nationalities[1]"})}
    run = drive(
        tmp_path, batch, POLICY, [keys["ec"].jwk()], holder
    )

    assert run.process.returncode == 0, run.process.stderr
    entry = entries(run.report)["shifted"]
    assert entry["status"] == "presented"
    assert [path for path in entry["disclosed"] if path.startswith("nationalities")] == [
        "nationalities[0]",
        "nationalities[1]",
        "nationalities[2]",
    ]


def test_release_is_the_smallest_across_alternative_groups(tmp_path, keys):
    """The released set is the global minimum, not each group's cheapest option on its own."""
    holder = keys["holder"]
    credential = ref.issue(keys["ec"], claims(holder), SD_PATHS, decoys=2, seed=61)
    run = drive(
        tmp_path, {"minimal": credential.issuance()}, POLICY, [keys["ec"].jwk()], holder
    )

    assert run.process.returncode == 0, run.process.stderr
    entry = entries(run.report)["minimal"]
    assert entry["status"] == "presented"
    assert entry["disclosed"] == [
        "given_name",
        "nationalities[0]",
        "nationalities[1]",
        "nationalities[2]",
        "residence",
        "residence.address",
        "residence.address.geo",
        "residence.address.geo.lat",
        "residence.address.geo.lon",
    ]


def test_ties_between_alternatives_follow_the_policy_order(tmp_path, keys):
    """When two ways of satisfying the policy cost the same, the earlier listed path wins."""
    holder = keys["holder"]
    credential = ref.issue(keys["ec"], claims(holder), SD_PATHS, decoys=1, seed=71)
    policy = {
        "required": ["given_name"],
        "alternatives": [["family_name", "contact.person.im", "work.site.desk"]],
    }
    run = drive(
        tmp_path, {"tied": credential.issuance()}, policy, [keys["ec"].jwk()], holder
    )

    assert run.process.returncode == 0, run.process.stderr
    entry = entries(run.report)["tied"]
    assert entry["disclosed"] == ["family_name", "given_name"]


def test_presentation_binds_the_released_disclosures_to_the_holder(tmp_path, keys):
    """A released presentation carries exactly the released disclosures under a valid key binding."""
    holder = keys["holder"]
    credential = ref.issue(keys["ec"], claims(holder), SD_PATHS, decoys=2, seed=81)
    run = drive(
        tmp_path, {"bound": credential.issuance()}, POLICY, [keys["ec"].jwk()], holder
    )

    assert run.process.returncode == 0, run.process.stderr
    presentation = ref.read_presentation(run.out, "bound")
    assert presentation is not None, "no presentation was written for a released credential"
    prefix, sd_hash, cnf = run.presentations["bound"]
    ref.check_key_binding(presentation, prefix, cnf, ref.DEFAULT_CONFIG)

    released = presentation[: presentation.rindex("~")].split("~")[1:]
    assert released == sorted(released, key=lambda text: text.encode("utf-8"))
    assert len(released) == len(entries(run.report)["bound"]["disclosed"])
    assert set(released) <= set(credential.disclosures)
    assert entries(run.report)["bound"]["sd_hash"] == sd_hash


def test_credentials_that_cannot_satisfy_the_policy_release_nothing(tmp_path, keys):
    """A credential short of the policy is reported insufficient with the paths it cannot cover."""
    holder = keys["holder"]
    thin = claims(
        holder,
        work=None,
        contact={"person": {"im": "rune#77"}},
        residence={"address": {"country": "NO"}},
    )
    credential = ref.issue(
        keys["ec"],
        thin,
        ["given_name", "contact", "contact.person", "contact.person.im", "nationalities[0]"],
        decoys=1,
        seed=91,
    )
    run = drive(
        tmp_path, {"thin": credential.issuance()}, POLICY, [keys["ec"].jwk()], holder
    )

    assert run.process.returncode == 0, run.process.stderr
    entry = entries(run.report)["thin"]
    assert entry["status"] == "insufficient"
    assert entry["missing"] == [
        "contact.person.email",
        "residence.address.geo.lat",
        "residence.address.geo.lon",
        "work.site.phone",
    ]
    assert "disclosed" not in entry
    assert os.listdir(os.path.join(run.out, "presentations")) == []


def test_only_usable_published_keys_are_reported_and_used(tmp_path, keys):
    """The key set is filtered to signature keys this profile can use, with RFC 7638 thumbprints."""
    holder = keys["holder"]
    unlabelled = ref.SigningKey("issuer-plain", "RSA", alg="RS256")
    encryption = ref.SigningKey("issuer-enc", "RSA", alg=None, use="enc")
    published = [
        keys["ec"].jwk(),
        unlabelled.jwk(include_alg=False),
        encryption.jwk(),
        {"kty": "EC", "crv": "P-384", "kid": "issuer-p384", "x": ref.b64u(b"x" * 48), "y": ref.b64u(b"y" * 48)},
        {"kty": "oct", "kid": "issuer-shared", "k": ref.b64u(b"0123456789abcdef")},
        {"kty": "EC", "crv": "P-256", "x": ref.b64u(b"x" * 32), "y": ref.b64u(b"y" * 32)},
    ]
    batch = {
        "labelled": ref.issue(keys["ec"], claims(holder), SD_PATHS, seed=101).issuance(),
        "plain": ref.issue(unlabelled, claims(holder), SD_PATHS, seed=102).issuance(),
        "anonymous": ref.issue(keys["ec"], claims(holder), SD_PATHS, seed=103, kid=False).issuance(),
    }
    run = drive(tmp_path, batch, POLICY, published, holder)

    assert run.process.returncode == 0, run.process.stderr
    document = json.loads(run.report)
    assert [entry["kid"] for entry in document["keys"]] == ["issuer-ec", "issuer-plain"]
    assert {entry["kid"]: entry["thumbprint"] for entry in document["keys"]} == {
        "issuer-ec": keys["ec"].thumbprint(),
        "issuer-plain": unlabelled.thumbprint(),
    }
    found = entries(run.report)
    assert found["labelled"]["kid"] == "issuer-ec"
    assert found["plain"]["status"] == "presented" and found["plain"]["alg"] == "RS256"
    assert found["anonymous"]["status"] == "presented" and found["anonymous"]["kid"] == "issuer-ec"


def test_broker_reads_the_issuer_key_set_it_is_pointed_at(tmp_path):
    """The issuer key set is read from the configured location, as a served URL and as a file."""
    issuer = ref.tck_keys()
    holder = ref.SigningKey("acme-wallet-mp", "EC")
    served = ref.published_key_set()
    batch = {
        "mp-ec": ref.issue(issuer["eckey"], claims(holder), SD_PATHS, decoys=2, seed=201).issuance(),
        "mp-rsa": ref.issue(
            issuer["rskey"], claims(holder, given_name="Tomas"), SD_PATHS, seed=202, spacing="compact"
        ).issuance(),
    }
    published = ref.usable_keys(served)
    expected_keys = {kid: ref.thumbprint_of(entry) for kid, entry in published.items()}
    assert expected_keys, "the environment ships no usable issuer key"

    with ref.JwksServer(served) as server:
        process, report, out = ref.run_broker(
            str(tmp_path / "url"), batch, POLICY, server.url, holder, ref.DEFAULT_CONFIG
        )
        _, presentations = ref.expected_report(
            batch, served, server.url, POLICY, ref.DEFAULT_CONFIG
        )
        assert process.returncode == 0, process.stderr
        assert server.hits >= 1, "the broker never read the location it was given"
        document = json.loads(report)
        assert document["jwks_uri"] == server.url
        assert {entry["kid"]: entry["thumbprint"] for entry in document["keys"]} == expected_keys
        found = entries(report)
        assert found["mp-ec"]["status"] == "presented" and found["mp-ec"]["alg"] == "ES256"
        assert found["mp-rsa"]["status"] == "presented" and found["mp-rsa"]["alg"] == "RS256"
        for name, (prefix, _, cnf) in presentations.items():
            ref.check_key_binding(ref.read_presentation(out, name), prefix, cnf, ref.DEFAULT_CONFIG)

    mirrored = "file://" + ref.ISSUER_JWKS
    process, report, _ = ref.run_broker(
        str(tmp_path / "file"), batch, POLICY, mirrored, holder, ref.DEFAULT_CONFIG
    )
    assert process.returncode == 0, process.stderr
    document = json.loads(report)
    assert document["jwks_uri"] == mirrored
    assert {entry["kid"]: entry["thumbprint"] for entry in document["keys"]} == expected_keys
    assert [entry["status"] for entry in document["credentials"]] == ["presented", "presented"]


def test_unreachable_key_set_stops_the_run(tmp_path, keys):
    """Nothing is reported when the issuer key set cannot be retrieved."""
    holder = keys["holder"]
    batch = {"atlas": ref.issue(keys["ec"], claims(holder), SD_PATHS, seed=301).issuance()}
    with ref.JwksServer({"keys": [keys["ec"].jwk()]}) as server:
        dead = server.url
    process, report, _ = ref.run_broker(str(tmp_path), batch, POLICY, dead, holder)

    assert process.returncode != 0, "a key set that cannot be read has to stop the run"
    assert report is None, "no report may be written when the key set is unavailable"

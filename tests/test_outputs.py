"""Behavioral verification for the retained NIST Beacon audit."""

import hashlib
import json
import os
import pathlib
import shutil
import subprocess

import pytest


APP = pathlib.Path("/app")
AUDIT = APP / "audit"
EVIDENCE = AUDIT / "evidence"
RECEIPT = AUDIT / "receipt.json"
CASE = APP / "cases" / "chain1-220390-220394.json"
CERTIFICATE_ID = (
    "5501E3D72BC42F3B96E16DE4DCADCB16768E109662BD16D667D5FD9AEE585AF3"
    "1BBDC5DD4F53592276064B53DDDD76C8F3604B2A41DB6E09F78F82BB5D6569E7"
)
EXPECTED = {
    220390: (
        "2018-12-26T16:03:00.000Z",
        "E317D2DC8DEAA4C5E91C0A90357CA2B0C04F0CAB5F0ABE109773ECDFB63B7850"
        "0563E6DFF7C8B4243820AFA39952562F5BE99238092AADAF75C7DD5D8534A1E4",
        "B9564A6C20BB47E2537F4FF8CF22C26413D9BF893C0FC52E64112B7D15CA978A"
        "948326C447930A17D36D25F3CD6DEEAB11BE496D0CCB7F700406824D66C57BB0",
    ),
    220391: (
        "2018-12-26T16:04:00.000Z",
        "EDBD7F83C2EDD95508A870A1A57FFA821A7E50B4C7FABEF6FC3B79D0BF6608A7"
        "36B8D6D75474DBEB91FE5DE59F0AE29E92844ADD7DF86A678CC906C992D8288C",
        "F19E748BA06A6AC30259250E8AF1623C0DA050AB006BC0BD396E96D9465F3431"
        "B760773AC68CC3B9C6AB5923C8059D68829D856E6D674A41621603D565766ECF",
    ),
    220392: (
        "2018-12-26T16:05:00.000Z",
        "2833B6A8891875955AD8854B2FC503A44A0A6A7B589A815340D32AC0ABE6FDFA"
        "3BAD71F5D6650E4F333B0B97A634A97ECF1E576EFE46E3A061416A407B1742E9",
        "34C364F419E643952092B7FB9176FB43483103254D978258F158080F8780E77A8"
        "A329D1AFF8A573D04D1FC1F9A7A78E554B19A56563354B501F8BD906379D9A8",
    ),
    220393: (
        "2018-12-26T16:06:00.000Z",
        "BA646CC4E7AE195D2C85E9D3AE9C9722B974F2134699D2493FA9E296C34995E8"
        "E471B329CB5F63235982CEE3395A749C618E61466847951D543ADC2FBAD23ECB",
        "22D5EC946E3F4AFBD12633C22A10CD3E3657CA487B1537CC0DC988F952B9B9C2"
        "95E445AA8795421A222785B7DC85E7BDF3DFFE1729D176D66B7F55D55D78716D",
    ),
    220394: (
        "2018-12-26T16:07:00.000Z",
        "0A8863E03E200F694CBA50F0F9A009B078555FE637B07CA2C0A0E4D5640801737"
        "87B26376C4762377A139D1BCAA916A10419504850EB7CF91552A17FDCAA0463",
        "28EACA6042EBE5DFBF3ECF479023A155A1C2D69E9C0064E36485F23681D83D36"
        "02BD85E4F6663A264F914219157104CDDB47C34940FA5789B8AB4DC57C64F246",
    ),
}


def sha512(path: pathlib.Path) -> str:
    """Return an uppercase SHA-512 digest for one retained artifact."""
    return hashlib.sha512(path.read_bytes()).hexdigest().upper()


def load_receipt() -> dict:
    """Load the submitted receipt as an ordered Python mapping."""
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def run_verify(case: pathlib.Path, evidence: pathlib.Path, receipt: pathlib.Path):
    """Run the installed verifier against an arbitrary runtime evidence set."""
    return subprocess.run(
        [
            "beacon-audit",
            "verify",
            "--case",
            str(case),
            "--directory",
            str(evidence),
            "--receipt",
            str(receipt),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.fixture(scope="session")
def fresh_chain(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """Generate a hidden, freshly signed chain that cannot be fixture-hardcoded."""
    root = tmp_path_factory.mktemp("fresh-chain")
    generator = pathlib.Path(__file__).with_name("fresh_chain.go")
    result = subprocess.run(
        ["go", "run", str(generator), "--directory", str(root)],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    return root


def copy_fresh(fresh_chain: pathlib.Path, tmp_path: pathlib.Path) -> pathlib.Path:
    target = tmp_path / "chain"
    shutil.copytree(fresh_chain, target)
    case_path = target / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["policy"] = str(target / "policy.json")
    case["trust"] = str(target / "trust.json")
    case_path.write_text(json.dumps(case), encoding="utf-8")
    receipt = target / "receipt.json"
    if receipt.exists():
        receipt.unlink()
    return target


def repin_pulse(root: pathlib.Path, index: int) -> None:
    """Update a generated case pin after a deliberate semantic mutation."""
    case_path = root / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["pulse_sha512"][str(index)] = sha512(
        root / "evidence" / f"pulse-{index}.json"
    )
    case_path.write_text(json.dumps(case), encoding="utf-8")


def test_evidence_layout_is_complete_and_safe() -> None:
    """The evidence set contains only the requested regular files."""
    assert EVIDENCE.is_dir() and not EVIDENCE.is_symlink()
    expected_names = {"certificate.pem"} | {
        f"pulse-{index}.json" for index in EXPECTED
    }
    assert {path.name for path in EVIDENCE.iterdir()} == expected_names
    for path in EVIDENCE.iterdir():
        assert path.is_file()
        assert not path.is_symlink()


def test_retained_bodies_are_authoritative_nist_responses() -> None:
    """Every pulse body matches the stable authoritative API evidence."""
    for index, (timestamp, output, digest) in EXPECTED.items():
        path = EVIDENCE / f"pulse-{index}.json"
        assert sha512(path) == digest
        pulse = json.loads(path.read_bytes())["pulse"]
        assert pulse["uri"] == (
            f"https://beacon.nist.gov/beacon/2.0/chain/1/pulse/{index}"
        )
        assert pulse["chainIndex"] == 1
        assert pulse["pulseIndex"] == index
        assert pulse["timeStamp"] == timestamp
        assert pulse["outputValue"] == output
        assert pulse["certificateId"].upper() == CERTIFICATE_ID
    assert sha512(EVIDENCE / "certificate.pem") == (
        "135CBCC3AB4580D893780D33A54C919F78FCE050F39900A4BC5A0652D3FBD8BE"
        "0B176E83374F0AFB08EC4EA712FF9D2BD5458A0177CF910FD186C3E9658F5617"
    )


def test_receipt_has_exact_top_level_contract() -> None:
    """The receipt exposes the ordered case, trust, result, and time fields."""
    receipt = load_receipt()
    assert list(receipt) == [
        "case_id",
        "api_origin",
        "chain_index",
        "first_pulse",
        "last_pulse",
        "certificate_id",
        "certificate_sha512",
        "policy_profile",
        "trust_profile",
        "pulses",
        "continuity",
        "audited_at",
        "result",
    ]
    assert receipt["case_id"] == "IR-2018-12-26-NIST-CHAIN1"
    assert receipt["api_origin"] == "https://beacon.nist.gov"
    assert (receipt["chain_index"], receipt["first_pulse"], receipt["last_pulse"]) == (
        1,
        220390,
        220394,
    )
    assert receipt["certificate_id"] == CERTIFICATE_ID
    assert receipt["certificate_sha512"] == CERTIFICATE_ID
    assert receipt["policy_profile"] == "nist-v2-strict"
    assert receipt["trust_profile"] == "nist-chain1-pinned-certificate"
    assert receipt["audited_at"] == "2018-12-26T16:07:00.000Z"
    assert receipt["result"] == "PASS"
    assert RECEIPT.read_bytes().endswith(b"\n")


def test_receipt_records_each_cryptographic_check() -> None:
    """Per-pulse receipt records bind evidence digests and verification results."""
    pulses = load_receipt()["pulses"]
    assert [pulse["index"] for pulse in pulses] == list(EXPECTED)
    for pulse in pulses:
        timestamp, output, digest = EXPECTED[pulse["index"]]
        assert list(pulse) == [
            "index",
            "timestamp",
            "source_uri",
            "evidence_file",
            "evidence_sha512",
            "output_value",
            "signature_verified",
            "output_hash_verified",
            "certificate_valid_at_pulse",
        ]
        assert pulse["timestamp"] == timestamp
        assert pulse["output_value"] == output
        assert pulse["evidence_sha512"] == digest
        assert pulse["evidence_file"] == f"pulse-{pulse['index']}.json"
        assert pulse["source_uri"].endswith(f"/pulse/{pulse['index']}")
        assert pulse["signature_verified"] is True
        assert pulse["output_hash_verified"] is True
        assert pulse["certificate_valid_at_pulse"] is True


def test_chain_continuity_is_fully_attested() -> None:
    """The receipt attests all four interval continuity properties."""
    continuity = load_receipt()["continuity"]
    assert list(continuity) == [
        "indexes_consecutive",
        "timestamps_consecutive",
        "previous_links_verified",
        "precommitments_verified",
    ]
    assert all(value is True for value in continuity.values())


def test_installed_tool_reproduces_receipt(tmp_path: pathlib.Path) -> None:
    """Fresh verification of retained evidence deterministically reproduces receipt."""
    regenerated = tmp_path / "receipt.json"
    result = subprocess.run(
        [
            "beacon-audit",
            "verify",
            "--case",
            str(CASE),
            "--directory",
            str(EVIDENCE),
            "--receipt",
            str(regenerated),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert regenerated.read_bytes() == RECEIPT.read_bytes()


def test_tampered_fresh_evidence_fails_closed(tmp_path: pathlib.Path) -> None:
    """Runtime-created pulse tampering is rejected without issuing a receipt."""
    copied = tmp_path / "evidence"
    shutil.copytree(EVIDENCE, copied)
    pulse_path = copied / "pulse-220392.json"
    pulse = json.loads(pulse_path.read_text(encoding="utf-8"))
    value = pulse["pulse"]["outputValue"]
    pulse["pulse"]["outputValue"] = ("0" if value[0] != "0" else "1") + value[1:]
    pulse_path.write_text(json.dumps(pulse), encoding="utf-8")
    attempted = tmp_path / "forged-receipt.json"
    result = subprocess.run(
        [
            "beacon-audit",
            "verify",
            "--case",
            str(CASE),
            "--directory",
            str(copied),
            "--receipt",
            str(attempted),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode != 0
    assert not attempted.exists()


def test_symlinked_fresh_evidence_fails_closed(tmp_path: pathlib.Path) -> None:
    """Runtime-created symlink substitution is rejected as unsafe evidence."""
    copied = tmp_path / "evidence"
    shutil.copytree(EVIDENCE, copied)
    target = copied / "pulse-220393.json"
    backup = tmp_path / "outside.json"
    shutil.copyfile(target, backup)
    target.unlink()
    os.symlink(backup, target)
    attempted = tmp_path / "symlink-receipt.json"
    result = subprocess.run(
        [
            "beacon-audit",
            "verify",
            "--case",
            str(CASE),
            "--directory",
            str(copied),
            "--receipt",
            str(attempted),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode != 0
    assert not attempted.exists()


def test_fresh_runtime_chain_verifies(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """The implementation verifies a newly generated signed chain."""
    root = copy_fresh(fresh_chain, tmp_path)
    receipt = root / "receipt.json"
    result = run_verify(root / "case.json", root / "evidence", receipt)
    assert result.returncode == 0, result.stderr
    body = json.loads(receipt.read_text(encoding="utf-8"))
    assert body["case_id"] == "FRESH-RUNTIME-CHAIN"
    assert [item["index"] for item in body["pulses"]] == [9001, 9002, 9003]
    assert body["result"] == "PASS"


@pytest.mark.parametrize("mutation", ["duplicate", "trailing"])
def test_noncanonical_json_is_rejected(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path, mutation: str
) -> None:
    """Duplicate keys and trailing JSON documents fail before receipt issuance."""
    root = copy_fresh(fresh_chain, tmp_path)
    pulse = root / "evidence" / "pulse-9002.json"
    raw = pulse.read_text(encoding="utf-8")
    if mutation == "duplicate":
        value = json.loads(raw)["pulse"]
        pulse.write_text(
            json.dumps({"pulse": value})[:-1]
            + ',"pulse":'
            + json.dumps(value)
            + "}",
            encoding="utf-8",
        )
    else:
        pulse.write_text(raw + "{}\n", encoding="utf-8")
    repin_pulse(root, 9002)
    receipt = root / "receipt.json"
    result = run_verify(root / "case.json", root / "evidence", receipt)
    assert result.returncode != 0
    assert not receipt.exists()


def test_weakened_strict_policy_is_rejected(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A policy cannot turn required cryptographic checks off."""
    root = copy_fresh(fresh_chain, tmp_path)
    policy_path = root / "policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["require_signatures"] = False
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    receipt = root / "receipt.json"
    result = run_verify(root / "case.json", root / "evidence", receipt)
    assert result.returncode != 0
    assert not receipt.exists()


def test_noncanonical_trust_profile_is_rejected(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Trust pins must be unique canonical uppercase SHA-512 values."""
    root = copy_fresh(fresh_chain, tmp_path)
    trust_path = root / "trust.json"
    trust = json.loads(trust_path.read_text(encoding="utf-8"))
    trust["allowed_certificate_ids"][0] = trust["allowed_certificate_ids"][0].lower()
    trust_path.write_text(json.dumps(trust), encoding="utf-8")
    receipt = root / "receipt.json"
    result = run_verify(root / "case.json", root / "evidence", receipt)
    assert result.returncode != 0
    assert not receipt.exists()


def test_case_body_pins_are_mandatory(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A fresh evidence body cannot diverge from its case SHA-512 manifest."""
    root = copy_fresh(fresh_chain, tmp_path)
    case_path = root / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["pulse_sha512"]["9002"] = "0" * 128
    case_path.write_text(json.dumps(case), encoding="utf-8")
    receipt = root / "receipt.json"
    result = run_verify(case_path, root / "evidence", receipt)
    assert result.returncode != 0
    assert not receipt.exists()


@pytest.mark.parametrize("mode", ["no-san", "ca", "no-digital"])
def test_unfit_signing_certificates_are_rejected(
    tmp_path: pathlib.Path, mode: str
) -> None:
    """Only the pinned DNS end-entity digital-signature certificate is accepted."""
    root = tmp_path / mode
    generator = pathlib.Path(__file__).with_name("fresh_chain.go")
    generated = subprocess.run(
        [
            "go",
            "run",
            str(generator),
            "--directory",
            str(root),
            "--certificate-mode",
            mode,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert generated.returncode == 0, generated.stderr
    receipt = root / "receipt.json"
    result = run_verify(root / "case.json", root / "evidence", receipt)
    assert result.returncode != 0
    assert not receipt.exists()


def test_duplicate_list_value_is_rejected_before_crypto(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Each required list-value type appears exactly once."""
    root = copy_fresh(fresh_chain, tmp_path)
    pulse_path = root / "evidence" / "pulse-9002.json"
    envelope = json.loads(pulse_path.read_text(encoding="utf-8"))
    envelope["pulse"]["listValues"].append(envelope["pulse"]["listValues"][0])
    pulse_path.write_text(json.dumps(envelope), encoding="utf-8")
    repin_pulse(root, 9002)
    receipt = root / "receipt.json"
    result = run_verify(root / "case.json", root / "evidence", receipt)
    assert result.returncode != 0
    assert not receipt.exists()


def test_foreign_list_uri_is_rejected(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A list value cannot claim provenance from a foreign chain origin."""
    root = copy_fresh(fresh_chain, tmp_path)
    pulse_path = root / "evidence" / "pulse-9002.json"
    envelope = json.loads(pulse_path.read_text(encoding="utf-8"))
    envelope["pulse"]["listValues"][1]["uri"] = (
        "https://example.com/beacon/2.0/chain/7/pulse/8999"
    )
    pulse_path.write_text(json.dumps(envelope), encoding="utf-8")
    repin_pulse(root, 9002)
    receipt = root / "receipt.json"
    result = run_verify(root / "case.json", root / "evidence", receipt)
    assert result.returncode != 0
    assert not receipt.exists()


def test_nonzero_signed_pulse_status_is_rejected(tmp_path: pathlib.Path) -> None:
    """A cryptographically valid pulse with a nonzero status still fails closed."""
    root = tmp_path / "nonzero"
    generator = pathlib.Path(__file__).with_name("fresh_chain.go")
    generated = subprocess.run(
        ["go", "run", str(generator), "--directory", str(root), "--status", "1"],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert generated.returncode == 0, generated.stderr
    receipt = root / "receipt.json"
    result = run_verify(root / "case.json", root / "evidence", receipt)
    assert result.returncode != 0
    assert not receipt.exists()


def test_extra_and_oversized_evidence_fail_closed(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """The evidence inventory and per-file size cap are exact."""
    extra = copy_fresh(fresh_chain, tmp_path / "extra")
    (extra / "evidence" / "notes.txt").write_text("not evidence", encoding="utf-8")
    result = run_verify(extra / "case.json", extra / "evidence", extra / "receipt.json")
    assert result.returncode != 0
    assert not (extra / "receipt.json").exists()

    oversized = copy_fresh(fresh_chain, tmp_path / "oversized")
    pulse_path = oversized / "evidence" / "pulse-9002.json"
    pulse_path.write_bytes(pulse_path.read_bytes() + b" " * (2 << 20))
    repin_pulse(oversized, 9002)
    result = run_verify(
        oversized / "case.json", oversized / "evidence", oversized / "receipt.json"
    )
    assert result.returncode != 0
    assert not (oversized / "receipt.json").exists()


def test_receipt_paths_fail_closed_without_clobbering(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Receipt writes cannot enter evidence or replace a symlink target."""
    root = copy_fresh(fresh_chain, tmp_path)
    inside = root / "evidence" / "receipt.json"
    result = run_verify(root / "case.json", root / "evidence", inside)
    assert result.returncode != 0
    assert not inside.exists()

    victim = root / "victim.txt"
    victim.write_text("KEEP\n", encoding="utf-8")
    linked = root / "receipt.json"
    linked.symlink_to(victim)
    result = run_verify(root / "case.json", root / "evidence", linked)
    assert result.returncode != 0
    assert victim.read_text(encoding="utf-8") == "KEEP\n"
    assert linked.is_symlink()


def test_failed_verification_preserves_existing_receipt(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A failed rerun never destroys a previously committed receipt."""
    root = copy_fresh(fresh_chain, tmp_path)
    receipt = root / "receipt.json"
    receipt.write_text("PREVIOUS-RECEIPT\n", encoding="utf-8")
    pulse = root / "evidence" / "pulse-9002.json"
    pulse.write_bytes(pulse.read_bytes().replace(b'"statusCode": 0', b'"statusCode": 9', 1))
    result = run_verify(root / "case.json", root / "evidence", receipt)
    assert result.returncode != 0
    assert receipt.read_text(encoding="utf-8") == "PREVIOUS-RECEIPT\n"


def test_url_userinfo_origin_confusion_is_rejected(tmp_path: pathlib.Path) -> None:
    """URL userinfo cannot disguise a case origin as the approved NIST host."""
    generator = pathlib.Path(__file__).with_name("fresh_chain.go")
    confused_root = tmp_path / "confused"
    generated = subprocess.run(
        [
            "go",
            "run",
            str(generator),
            "--directory",
            str(confused_root),
            "--origin",
            "https://attacker@beacon.nist.gov",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert generated.returncode == 0, generated.stderr
    confused = run_verify(
        confused_root / "case.json",
        confused_root / "evidence",
        confused_root / "receipt.json",
    )
    assert confused.returncode != 0
    assert not (confused_root / "receipt.json").exists()


def test_symlinked_acquisition_destination_is_rejected(
    fresh_chain: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Acquisition refuses a symlinked destination without touching its target."""
    root = copy_fresh(fresh_chain, tmp_path / "symlink")
    case_path = root / "case.json"
    outside = root / "outside"
    outside.mkdir()
    destination = root / "acquired"
    destination.symlink_to(outside, target_is_directory=True)
    acquired = subprocess.run(
        [
            "beacon-audit",
            "acquire",
            "--case",
            str(case_path),
            "--directory",
            str(destination),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert acquired.returncode != 0
    assert "not a safe directory" in acquired.stderr
    assert not any(outside.iterdir())

import csv
import hashlib
import json
import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path

import pytest
from reference.generator import instance, write_challenge

VISIBLE_CHALLENGE = Path("/app/challenge")
VISIBLE_SECRET = Path("/tests/reference/visible_secret.json")
FLAG_RE = re.compile(r"^CICADA\{[0-9a-f]+\}$")


def parse_int(text):
    value = str(text).strip()
    if value.startswith("0x"):
        return int(value, 16)
    return int(value)


def read_public(path):
    out = {}
    for line in (path / "public.txt").read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        out[key] = parse_int(value)
    return out


def read_records(path):
    with (path / "ciphertexts.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows and rows[0].keys() == {"id", "a", "b", "ciphertext"}
    return [
        {
            "id": row["id"],
            "a": parse_int(row["a"]),
            "b": parse_int(row["b"]),
            "ciphertext": parse_int(row["ciphertext"]),
        }
        for row in rows
    ]


def read_relation(path):
    out = {}
    for line in (path / "relation.txt").read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        out[key] = parse_int(value)
    return out


def read_challenge(path):
    return {
        **read_public(path),
        **read_relation(path),
        "commitment": (path / "commitment.txt").read_text(encoding="utf-8").strip(),
        "records": read_records(path),
    }


def read_secret(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for key, value in data.items():
        if isinstance(value, str) and value.startswith("0x"):
            out[key] = int(value, 16)
        elif key == "records":
            out[key] = [
                {
                    **row,
                    "a": parse_int(row["a"]),
                    "b": parse_int(row["b"]),
                    "ciphertext": parse_int(row["ciphertext"]),
                    "source_m": parse_int(row["source_m"]),
                }
                for row in value
            ]
        else:
            out[key] = value
    return out


def candidate_output(prefix):
    directory = Path(tempfile.mkdtemp(prefix=prefix, dir="/tmp"))
    directory.chmod(0o777)
    return directory / "flag.txt"


def run_candidate(challenge, output, timeout=180):
    output.parent.chmod(0o777)
    proc = subprocess.run(
        [
            "setpriv",
            "--no-new-privs",
            "--reuid=10001",
            "--regid=10001",
            "--clear-groups",
            "go",
            "run",
            "/app/cmd/recover.go",
            str(challenge),
            str(output),
        ],
        cwd="/app",
        env={
            **os.environ,
            "HOME": "/home/candidate",
            "GOCACHE": "/tmp/candidate-go-cache",
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    raw_output = output.read_text(encoding="utf-8") if output.exists() else ""
    return {"proc": proc, "flag": raw_output.strip(), "raw_output": raw_output}


def run_naive(challenge, output, timeout=60):
    proc = subprocess.run(
        [
            "go",
            "run",
            "/tests/reference/naive_reference.go",
            str(challenge),
            str(output),
        ],
        cwd="/app",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    flag = output.read_text(encoding="utf-8").strip() if output.exists() else ""
    return {"proc": proc, "flag": flag}


@pytest.fixture(scope="session")
def hidden_material():
    hidden = instance(
        "hidden-" + secrets.token_hex(16),
        exponent=secrets.choice((29, 31, 37)),
        chunk_count=secrets.choice((9, 10)),
    )
    target = Path(tempfile.mkdtemp(prefix="rsa-affine-hidden-", dir="/tmp"))
    target.chmod(0o755)
    write_challenge(target, hidden)
    for path in target.iterdir():
        path.chmod(0o644)
    return {"path": target, "secret": hidden}


@pytest.fixture(scope="session")
def hidden_challenge_path(hidden_material):
    return hidden_material["path"]


@pytest.fixture(scope="session")
def visible_challenge():
    return read_challenge(VISIBLE_CHALLENGE)


@pytest.fixture(scope="session")
def hidden_challenge(hidden_challenge_path):
    return read_challenge(hidden_challenge_path)


@pytest.fixture(scope="session")
def visible_secret():
    return read_secret(VISIBLE_SECRET)


@pytest.fixture(scope="session")
def hidden_secret(hidden_material):
    return hidden_material["secret"]


@pytest.fixture(scope="session")
def visible_run():
    out = candidate_output("rsa-visible-")
    return run_candidate(VISIBLE_CHALLENGE, out)


@pytest.fixture(scope="session")
def hidden_run(hidden_challenge_path):
    out = candidate_output("rsa-hidden-")
    return run_candidate(hidden_challenge_path, out)


@pytest.fixture(scope="session")
def naive_visible(tmp_path_factory):
    out = tmp_path_factory.mktemp("naive_visible") / "flag.txt"
    return run_naive(VISIBLE_CHALLENGE, out)


@pytest.fixture(scope="session")
def naive_hidden(tmp_path_factory, hidden_challenge_path):
    out = tmp_path_factory.mktemp("naive_hidden") / "flag.txt"
    return run_naive(hidden_challenge_path, out)


def valid_records(secret):
    return [row for row in secret["records"] if row["source"] == "fragment"]


def decoy_records(secret):
    return [row for row in secret["records"] if row["source"] == "decoy"]


def poison_records(secret):
    return [row for row in secret["records"] if row["source"] == "poison"]


def by_id(rows):
    return {row["id"]: row for row in rows}


def assert_command_success(run):
    assert run["proc"].returncode == 0, run["proc"].stderr


def assert_records_match_secret(challenge, secret):
    actual = by_id(challenge["records"])
    expected = by_id(secret["records"])
    assert set(actual) == set(expected)
    for record_id, row in actual.items():
        exp = expected[record_id]
        assert row["a"] == exp["a"]
        assert row["b"] == exp["b"]
        assert row["ciphertext"] == exp["ciphertext"]


def assert_affine_generation(challenge, secret):
    assert challenge["n"] == secret["p"] * secret["q"]
    assert challenge["e"] == secret["e"]
    assert challenge["e"] in {29, 31, 37}
    assert challenge["commitment"] == secret["commitment"]
    assert challenge["multiplier"] == secret["multiplier"]
    assert challenge["lag_multiplier"] == secret["lag_multiplier"]
    assert challenge["third_multiplier"] == secret["third_multiplier"]
    assert challenge["increment"] == secret["increment"]
    assert challenge["modulus"] == 1 << 40
    assert challenge["chunk_count"] == secret["chunk_count"]
    assert challenge["share_count"] == secret["share_count"]
    assert challenge["share_bits"] == 40
    assert hashlib.sha256(secret["flag"].encode()).hexdigest() == secret["commitment"]
    flag_int = int.from_bytes(secret["flag"].encode(), "big")
    flag_cipher = pow(flag_int, challenge["e"], challenge["n"])
    assert all(row["ciphertext"] != flag_cipher for row in challenge["records"])
    assert all((row["a"], row["b"]) != (1, 0) for row in challenge["records"])
    message_ints = {
        int.from_bytes(message["text"].encode(), "big"): (
            message["index"],
            message["share"],
        )
        for message in secret["messages"]
    }
    seen = {message_int: 0 for message_int in message_ints}
    for row in secret["records"]:
        transformed = (row["a"] * row["source_m"] + row["b"]) % challenge["n"]
        assert pow(transformed, challenge["e"], challenge["n"]) == row["ciphertext"]
        if row["source"] == "fragment":
            assert row["source_m"] in message_ints
            assert row["source_index"] == message_ints[row["source_m"]][0]
            seen[row["source_m"]] += 1
        if row["source"] != "fragment":
            assert row["source_m"] not in message_ints
    assert set(seen.values()) == {2}
    body = secret["flag"][7:-1]
    chunks = []
    for index in range(secret["chunk_count"]):
        shares = [
            int(message["text"].split(":", 1)[1], 16)
            for message in secret["messages"]
            if message["index"] == index
        ]
        assert len(shares) == secret["share_count"]
        combined = 0
        for share in shares:
            combined ^= share
        expected = int(body[index * 10 : (index + 1) * 10], 16)
        assert combined == expected
        chunks.append(combined)
    for index in range(3, len(chunks)):
        assert chunks[index] == (
            secret["multiplier"] * chunks[index - 1]
            + secret["lag_multiplier"] * chunks[index - 2]
            + secret["third_multiplier"] * chunks[index - 3]
            + secret["increment"]
        ) & ((1 << 40) - 1)


def assert_no_easy_pair_order(secret):
    first_two = secret["records"][:2]
    assert first_two[0]["source_m"] != first_two[1]["source_m"]


def assert_record_ids_do_not_mark_source(secret):
    ids = [row["id"] for row in secret["records"]]
    assert ids == [f"c{index:02d}" for index in range(1, len(ids) + 1)]
    assert all(not row["id"].startswith(("r", "d")) for row in secret["records"])


def test_visible_command_exits_successfully(visible_run):
    """Visible command exits successfully."""
    assert_command_success(visible_run)


def test_hidden_command_exits_successfully(hidden_run):
    """Hidden command exits successfully."""
    assert_command_success(hidden_run)


def test_visible_flag_matches_secret(visible_run, visible_secret):
    """Visible flag matches secret."""
    assert visible_run["flag"] == visible_secret["flag"]


def test_hidden_flag_matches_secret(hidden_run, hidden_secret):
    """Hidden flag matches secret."""
    assert hidden_run["flag"] == hidden_secret["flag"]


def test_visible_flag_schema(visible_run):
    """Visible flag schema is exact."""
    assert FLAG_RE.fullmatch(visible_run["flag"])
    assert len(visible_run["flag"][7:-1]) % 10 == 0
    assert visible_run["raw_output"] == visible_run["flag"] + "\n"


def test_hidden_flag_schema(hidden_run):
    """Hidden flag schema is exact."""
    assert FLAG_RE.fullmatch(hidden_run["flag"])
    assert len(hidden_run["flag"][7:-1]) % 10 == 0
    assert hidden_run["raw_output"] == hidden_run["flag"] + "\n"


def test_naive_visible_does_not_recover(naive_visible, visible_secret):
    """Naive visible reference does not recover the flag."""
    assert naive_visible["proc"].returncode == 0, naive_visible["proc"].stderr
    assert FLAG_RE.fullmatch(naive_visible["flag"])
    assert naive_visible["flag"] != visible_secret["flag"]


def test_naive_hidden_does_not_recover(naive_hidden, hidden_secret):
    """Naive hidden reference does not recover the flag."""
    assert naive_hidden["proc"].returncode == 0, naive_hidden["proc"].stderr
    assert FLAG_RE.fullmatch(naive_hidden["flag"])
    assert naive_hidden["flag"] != hidden_secret["flag"]


def test_visible_records_match_secret_manifest(visible_challenge, visible_secret):
    """Visible public records match the hidden manifest."""
    assert_records_match_secret(visible_challenge, visible_secret)


def test_hidden_records_match_secret_manifest(hidden_challenge, hidden_secret):
    """Hidden public records match the hidden manifest."""
    assert_records_match_secret(hidden_challenge, hidden_secret)


def test_visible_affine_records_are_noisy(visible_challenge, visible_secret):
    """Visible records contain valid affine rows and decoys."""
    assert len(valid_records(visible_secret)) == (
        2 * visible_secret["chunk_count"] * visible_secret["share_count"]
    )
    assert len(poison_records(visible_secret)) == (
        2
        * visible_secret["chunk_count"]
        * visible_secret["share_count"]
        * visible_secret["poison_choices"]
    )
    assert len(decoy_records(visible_secret)) == 20
    assert_affine_generation(visible_challenge, visible_secret)
    assert_no_easy_pair_order(visible_secret)
    assert_record_ids_do_not_mark_source(visible_secret)


def test_hidden_affine_records_are_noisy(hidden_challenge, hidden_secret):
    """Hidden records contain valid affine rows and decoys."""
    assert len(valid_records(hidden_secret)) == (
        2 * hidden_secret["chunk_count"] * hidden_secret["share_count"]
    )
    assert len(poison_records(hidden_secret)) == (
        2
        * hidden_secret["chunk_count"]
        * hidden_secret["share_count"]
        * hidden_secret["poison_choices"]
    )
    assert len(decoy_records(hidden_secret)) == 20
    assert_affine_generation(hidden_challenge, hidden_secret)
    assert_no_easy_pair_order(hidden_secret)
    assert_record_ids_do_not_mark_source(hidden_secret)


def test_poison_groups_are_plausible_and_repeated(visible_secret, hidden_secret):
    """Each case contains repeated fragment-shaped poison plaintexts."""
    for secret in (visible_secret, hidden_secret):
        pattern = re.compile(r"^frag(?:[0-9]+)\.(?:[0-9]+):[0-9a-f]{10}$")
        texts = [message["text"] for message in secret["poison_messages"]]
        assert len(texts) == (
            secret["chunk_count"] * secret["share_count"] * secret["poison_choices"]
        )
        assert len(set(texts)) == len(texts)
        assert all(pattern.fullmatch(text) for text in texts)
        assert all(
            0 <= int(text.split(".", 1)[0][4:]) < secret["chunk_count"]
            and 0 <= int(text.split(".", 1)[1].split(":", 1)[0]) < secret["share_count"]
            for text in texts
        )
        labels = [text.split(":", 1)[0] for text in texts]
        assert set(labels.count(label) for label in set(labels)) == {
            secret["poison_choices"]
        }
        counts = {}
        for row in poison_records(secret):
            counts[row["source_m"]] = counts.get(row["source_m"], 0) + 1
        assert set(counts.values()) == {2}


def test_hidden_instance_is_fresh(visible_secret, hidden_secret):
    """The runtime-generated private case differs from the visible challenge."""
    assert visible_secret["n"] != hidden_secret["n"]
    assert visible_secret["flag"] != hidden_secret["flag"]
    assert visible_secret["chunk_count"] in {9, 10}
    assert hidden_secret["chunk_count"] in {9, 10}

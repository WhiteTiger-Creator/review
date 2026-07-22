import json
import shutil
import subprocess
from pathlib import Path

OUT_BLOB = Path("/app/output/pol_blob.bin")
OUT_VIEW = Path("/app/output/settle_view.json")
STUB = Path("/app/environment/data/stub_trace.json")
BUDGET = Path("/app/environment/data/lim/budgets.toml")
BANKS = "/app/environment/data/banks/sha1.json,/app/environment/data/banks/sha256.json"
NV = Path("/app/environment/data/nv/counter_seed.bin")
PROFILES = Path("/app/environment/data/profiles")
PHASE = Path("/app/var/phase.jsonl")
DURABLE = Path("/app/var/durable.json")
LIVE = Path("/app/var/nv_live.bin")
SEAT = Path("/app/var/seat.lock")
GENS = Path("/app/var/gens")

PUBLIC_ARMS = "alpha,bravo,charlie"
HELD_ARMS = "alpha,bravo,charlie,held_x2"
PREP = 7


def build() -> None:
    subprocess.run(
        ["bash", "/app/environment/tools/mk_all.sh"],
        cwd="/app",
        check=True,
        text=True,
        capture_output=True,
    )


def sha256_hex(data: bytes) -> str:
    proc = subprocess.run(["sha256sum"], input=data, check=True, capture_output=True)
    return proc.stdout.decode().split()[0]


def max_blob_bytes() -> int:
    for line in BUDGET.read_text().splitlines():
        if line.startswith("max_blob_bytes"):
            return int(line.split("=", 1)[1].strip())
    return 190


def seat(arms: str, prep: int = PREP) -> None:
    Path("/app/var").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["/app/bin/lab", "seat", "--prep", str(prep), "--banks", BANKS, "--arms", arms],
        cwd="/app",
        check=True,
        capture_output=True,
        text=True,
    )


def weave(arms: str) -> None:
    subprocess.run(
        ["/app/bin/lab", "weave", "--arms", arms],
        cwd="/app",
        check=True,
        capture_output=True,
        text=True,
    )


def seal() -> dict:
    OUT_BLOB.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "/app/bin/lab",
            "seal",
            "--nv",
            "/app/environment/data/nv/counter_seed.bin",
            "--out-blob",
            "/app/output/pol_blob.bin",
            "--out-view",
            "/app/output/settle_view.json",
        ],
        cwd="/app",
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(OUT_VIEW.read_text())


def synth(arms: str = PUBLIC_ARMS, prep: int = PREP) -> dict:
    OUT_BLOB.parent.mkdir(parents=True, exist_ok=True)
    Path("/app/var").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "/app/bin/lab",
            "synth",
            "--prep",
            str(prep),
            "--banks",
            BANKS,
            "--arms",
            arms,
            "--nv",
            "/app/environment/data/nv/counter_seed.bin",
            "--out-blob",
            "/app/output/pol_blob.bin",
            "--out-view",
            "/app/output/settle_view.json",
        ],
        cwd="/app",
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(OUT_VIEW.read_text())


def soft_reboot() -> None:
    subprocess.run(
        ["bash", "/app/environment/tools/softtpm_boot.sh"],
        check=True,
        capture_output=True,
        text=True,
    )


def soft_unseal(name: str, *, reboot: bool = True) -> None:
    if reboot:
        soft_reboot()
    subprocess.run(
        [
            "/app/bin/lab_tpm",
            "unseal",
            "--blob",
            "/app/output/pol_blob.bin",
            "--fixture",
            f"/app/environment/data/profiles/{name}.json",
            "--nv-live",
            "/app/var/nv_live.bin",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def recover() -> None:
    subprocess.run(["/app/bin/lab", "recover"], check=True, capture_output=True, text=True)


def replay() -> dict:
    subprocess.run(
        ["/app/bin/lab", "replay", "--out-view", "/app/output/settle_view.json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(OUT_VIEW.read_text())


def lineage_hex(doc: dict) -> str:
    raw = (
        f"{doc['bank_tag']}|{doc['nv_token']}|{doc['view_digest']}|"
        f"{doc['epoch']}|{doc['arms_digest']}"
    )
    return sha256_hex(raw.encode())


def assert_view(doc: dict, arms_csv: str, prep: int = PREP) -> None:
    assert isinstance(doc.get("arms"), list) and doc["arms"]
    want = [a.strip() for a in arms_csv.split(",") if a.strip()]
    got = [a["name"] for a in doc["arms"]]
    assert got == want
    assert doc["byte_len"] == len(OUT_BLOB.read_bytes())
    assert doc["byte_len"] <= max_blob_bytes()
    assert isinstance(doc["view_digest"], str) and len(doc["view_digest"]) == 64
    assert doc["view_digest"] != "0" * 64
    assert doc.get("nv_token")
    assert doc.get("bank_tag") == "sha256"
    assert doc.get("epoch") == prep
    assert doc.get("arms_digest") == sha256_hex(arms_csv.encode())
    assert doc.get("sync_label") == "settled"
    assert isinstance(doc.get("phase_digest"), str) and len(doc["phase_digest"]) == 64
    assert doc["phase_digest"] != "0" * 64
    assert doc.get("lineage_hex") == lineage_hex(doc)
    assert PHASE.is_file()
    assert doc["phase_digest"] == sha256_hex(PHASE.read_bytes())


class TestRkPublic:
    def test_rk_k1_seat_stale(self) -> None:
        """Weave rejects arm-list drift after seat without re-pinning."""
        build()
        seat(PUBLIC_ARMS, prep=4)
        bad = subprocess.run(
            ["/app/bin/lab", "weave", "--arms", HELD_ARMS],
            cwd="/app",
            capture_output=True,
            text=True,
        )
        assert bad.returncode != 0
        seat(HELD_ARMS, prep=4)
        weave(HELD_ARMS)
        doc = seal()
        assert_view(doc, HELD_ARMS, prep=4)
        assert SEAT.is_file()
        assert json.loads(SEAT.read_text())["arms_digest"] == doc["arms_digest"]

    def test_rk_k2_bank_epoch_token(self) -> None:
        """Viable bank is sha256; Soft-TPM accepts epoch-bound NV token."""
        build()
        doc = synth(PUBLIC_ARMS, prep=9)
        assert_view(doc, PUBLIC_ARMS, prep=9)
        bank = json.loads(Path("/app/environment/data/banks/sha256.json").read_text())
        sums = {e["name"]: e["sum"] for e in bank["entries"]}
        for arm in doc["arms"]:
            assert arm["sum"] == sums[arm["name"]]
        soft_unseal("alpha")
        soft_unseal("charlie")

    def test_rk_k3_held_order(self) -> None:
        """Held-out underscore ids keep coverage and request order under budget."""
        build()
        doc = synth(HELD_ARMS, prep=6)
        assert_view(doc, HELD_ARMS, prep=6)
        soft_unseal("held_x2")
        soft_unseal("bravo")

    def test_rk_k4_phase_epoch(self) -> None:
        """Phase journal records fold/pack/bind with matching epoch."""
        build()
        synth(PUBLIC_ARMS, prep=5)
        stages = []
        epochs = []
        for line in PHASE.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            stages.append(obj["stage"])
            epochs.append(obj["epoch"])
        assert stages == ["fold", "pack", "bind"]
        assert epochs == [5, 5, 5]

    def test_rk_k5_gen_snapshot(self) -> None:
        """Generation snapshot and durable state survive Soft-TPM reboot."""
        build()
        doc = synth(PUBLIC_ARMS, prep=8)
        token = doc["nv_token"]
        snap = GENS / "8"
        assert (snap / "blob.bin").is_file()
        assert (snap / "view.json").is_file()
        assert (snap / "seed.bin").is_file()
        soft_reboot()
        soft_unseal("bravo")
        dur = json.loads(DURABLE.read_text())
        assert dur.get("epoch") == 8
        assert dur.get("nv_token") == token
        assert dur.get("arms_digest") == doc["arms_digest"]
        assert isinstance(dur.get("seed_hex"), str) and len(dur["seed_hex"]) == 16

    def test_rk_k6_corrupt_recover(self) -> None:
        """After live NV wipe, recover restores unsealability from gens snapshot."""
        build()
        doc = synth(HELD_ARMS, prep=11)
        assert_view(doc, HELD_ARMS, prep=11)
        LIVE.write_bytes(b"\x00" * 8)
        DURABLE.write_text('{"epoch":0,"seed_hex":""}\n')
        recover()
        soft_unseal("alpha", reboot=False)
        soft_unseal("held_x2", reboot=False)

    def test_rk_k7_replay_idem(self) -> None:
        """Replay restores settle_view; same-prep re-synth keeps view_digest."""
        build()
        first = synth(PUBLIC_ARMS, prep=3)
        blob_digest = sha256_hex(OUT_BLOB.read_bytes())
        assert first["view_digest"] == blob_digest
        phase_after = sha256_hex(PHASE.read_bytes())
        assert first["phase_digest"] == phase_after
        OUT_VIEW.unlink()
        second = replay()
        assert second["view_digest"] == blob_digest
        assert sha256_hex(OUT_BLOB.read_bytes()) == blob_digest
        third = synth(PUBLIC_ARMS, prep=3)
        assert third["view_digest"] == blob_digest
        assert third["phase_digest"] == sha256_hex(PHASE.read_bytes())
        assert sha256_hex(PHASE.read_bytes()) == phase_after

    def test_rk_k8_cross_chain(self) -> None:
        """Stub overwrite, staged seat/weave/seal, and full held unseal converge."""
        build()
        shutil.copy(STUB, OUT_VIEW)
        stub = json.loads(STUB.read_text())
        seat(HELD_ARMS, prep=12)
        weave(HELD_ARMS)
        doc = seal()
        assert_view(doc, HELD_ARMS, prep=12)
        assert doc["arms"][0]["name"] != stub["arms"][0]["name"]
        assert doc["byte_len"] <= max_blob_bytes()
        for name in ("alpha", "bravo", "charlie", "held_x2"):
            soft_unseal(name)

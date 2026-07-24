import json
import subprocess
from pathlib import Path

ADMIT = "/app/admit-repo"
POLICY = "/app/policy/signer_matrix.toml"
RULES = "/app/policy/release_rules.toml"
KEY_HOME = "/app/environment/fixtures/keys/gnupg"
ENV = Path("/app/environment")
REPOS = ENV / "fixtures/repos"
REPORT = Path("/app/output/object_trust_report.json")


def _fixture_ids() -> list[str]:
    raw = (ENV / "docs/case_ids.txt").read_text().strip()
    return [part.strip() for part in raw.split(",") if part.strip()]


def _repo_for(index: int) -> Path:
    return REPOS / _fixture_ids()[index]


def _run_admit(repo: Path, release_ref: str) -> tuple[int, dict]:
    REPORT.unlink(missing_ok=True)
    proc = subprocess.run(
        [
            ADMIT,
            "--repo",
            str(repo),
            "--release-ref",
            release_ref,
            "--policy",
            POLICY,
            "--rules",
            RULES,
            "--report",
            str(REPORT),
            "--key-home",
            KEY_HOME,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert REPORT.exists(), proc.stderr + proc.stdout
    data = json.loads(REPORT.read_text())
    assert len(data.get("walk_digest", "")) == 64
    assert isinstance(data.get("walk_records"), list)
    assert data.get("schema_version") == 1
    assert "walk_digest" in data
    assert "admitted" in data
    return proc.returncode, data


def test_k4_mv_pair():
    """Replace-aware walk must reject when closure includes unsigned parent commits."""
    code, rep = _run_admit(_repo_for(0), "release")
    assert code == 2
    assert rep["admitted"] is False
    assert len(rep["walk_records"]) >= 2
    assert rep["rejection"]["code"] in {"TAG_ANCHOR", "RPL_MAP"}


def test_q7_z2_emit():
    """Renamed release refs must not bypass admission via hard-coded ref names."""
    subprocess.run(
        [
            "python3",
            "/app/environment/fixtures/gen/replay_mutator.py",
            "/app/environment/fixtures/repos/arm_rpl_a7",
            "/tmp/git_trust_replay_perm",
            "--release-ref",
            "release",
            "--alt-name",
            "ship_line",
        ],
        check=True,
    )
    code, rep = _run_admit(Path("/tmp/git_trust_replay_perm"), "ship_line")
    assert code == 2
    assert rep["admitted"] is False


def test_h3_wx_cycle():
    """Shallow boundary fixtures must emit SHLW_GAP rejections."""
    code, rep = _run_admit(_repo_for(1), "release")
    assert code == 2
    assert rep["admitted"] is False
    assert rep["rejection"]["code"] == "SHLW_GAP"


def test_j9_n4_span():
    """Shallow arms must keep non-admitted status with populated walk records."""
    _, rep = _run_admit(_repo_for(1), "release")
    assert not rep["admitted"]
    assert len(rep["walk_records"]) >= 1


def test_p2_r8_bind():
    """Signed tags cannot cover unsigned commit payloads without closure anchors."""
    code, rep = _run_admit(_repo_for(2), "v1.0")
    assert code == 2
    assert rep["rejection"]["code"] == "TAG_ANCHOR"


def test_v5_t1_fork():
    """Transitional principal lane must admit commits signed with rel_b."""
    code, rep = _run_admit(_repo_for(3), "release")
    assert code == 0
    assert rep["admitted"] is True


def test_idempotent_rerun():
    """Consecutive runs with identical inputs must produce identical reports."""
    _run_admit(_repo_for(3), "release")
    first = REPORT.read_text()
    _run_admit(_repo_for(3), "release")
    second = REPORT.read_text()
    assert first == second

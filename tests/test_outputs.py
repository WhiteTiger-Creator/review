import grp
import json
import os
import pwd
import shutil
import subprocess
from pathlib import Path

import pytest
from reference.crystal_cellar_reference import ALL_CASES, HAND_CASES, solve

APP_DIR = Path(os.environ.get("APP_DIR", "/app"))
STAGE_DIR = APP_DIR / ".crystal-cellar-verifier-stage"
ENTRYPOINT = STAGE_DIR / "bin" / "crystal-cellar-push"
RUBY = shutil.which("ruby") or "ruby"


@pytest.fixture(scope="session", autouse=True)
def stage_crystal_cellar_source():
    """Copy only runnable Ruby source into a clean stage and syntax-check it."""
    shutil.rmtree(STAGE_DIR, ignore_errors=True)
    for root_name in ("bin", "lib"):
        source_root = APP_DIR / root_name
        assert source_root.is_dir()
        for path in source_root.rglob("*"):
            assert not path.is_symlink(), f"source symlink is not allowed: {path}"
        shutil.copytree(source_root, STAGE_DIR / root_name)

    for path in STAGE_DIR.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    assert ENTRYPOINT.is_file()

    ruby_sources = [ENTRYPOINT, *sorted((STAGE_DIR / "lib").rglob("*.rb"))]
    for source in ruby_sources:
        result = subprocess.run(
            [RUBY, "-c", str(source)],
            cwd=STAGE_DIR,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr

    yield
    shutil.rmtree(STAGE_DIR, ignore_errors=True)


def _drop_to_nobody():
    account = pwd.getpwnam("nobody")
    group = grp.getgrnam("nogroup")
    os.setgroups([])
    os.setgid(group.gr_gid)
    os.setuid(account.pw_uid)


def run_case(input_text: str) -> str:
    command = [RUBY, str(ENTRYPOINT)]
    demote = None
    if os.name != "nt" and APP_DIR == Path("/app"):
        demote = _drop_to_nobody
    result = subprocess.run(
        command,
        check=False,
        input=input_text,
        cwd=STAGE_DIR,
        capture_output=True,
        text=True,
        timeout=10,
        preexec_fn=demote,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    return result.stdout


@pytest.mark.parametrize("case", HAND_CASES, ids=[case.name for case in HAND_CASES])
def test_named_rule_families(case):
    """Named boards cover walking, pushes, gates, ice, and blocked routes."""
    assert run_case(case.to_input()) == solve(case)


@pytest.mark.parametrize("case", ALL_CASES[12:], ids=[case.name for case in ALL_CASES[12:]])
def test_generated_boundary_corpus(case):
    """Boundary boards vary corridor length, ice length, and lock placement."""
    assert run_case(case.to_input()) == solve(case)


def test_batch_output_keeps_input_order():
    cases = [ALL_CASES[5], ALL_CASES[0], ALL_CASES[14], ALL_CASES[11]]
    header = f"{len(cases)}\n"
    body = "".join(
        f"{case.name} {len(case.rows)} {len(case.rows[0])}\n" + "\n".join(case.rows) + "\n"
        for case in cases
    )
    expected = "".join(solve(case) for case in cases)
    assert run_case(header + body) == expected


def test_examples_file_matches_public_contract():
    examples = json.loads((APP_DIR / "examples.json").read_text())
    for entry in examples:
        assert run_case(entry["input"]) == entry["output"]


def test_answer_material_is_not_reachable_by_candidate_process():
    assert not (STAGE_DIR / "tests").exists()
    assert not (STAGE_DIR / "solution").exists()
    assert {path.name for path in STAGE_DIR.iterdir()} == {"bin", "lib"}
    if os.name == "nt" or APP_DIR != Path("/app"):
        pytest.skip("permission check only applies inside the Linux task image")
    probe = subprocess.run(
        [
            "su",
            "-s",
            "/bin/bash",
            "nobody",
            "-c",
            "cat /tests/reference/crystal_cellar_reference.py",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert probe.returncode != 0

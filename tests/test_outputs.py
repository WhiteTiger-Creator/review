"""Behavioral verifier tests for GraphRunSigner recovery and signing."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import verifier_support as vs
from jsonschema import Draft7Validator

APP = Path("/app/pkg")
SCRIPTS = Path("/app/pkg/ops")
OUTPUT = Path("/output")
MANIFEST_SCHEMA = Path("/app/docs/signing-manifest.schema.json")


@pytest.fixture(scope="session")
def gradle_home(tmp_path_factory):
    home = tmp_path_factory.mktemp("gradle-home")
    vs.seed_gradle_home(home)
    return home


def test_project_builds_from_clean_gradle_home_offline(gradle_home):
    """Service and release mirror must assemble offline from a clean Gradle home."""
    env = {
        "GRADLE_USER_HOME": str(gradle_home),
        "GRADLE_BIN": os.environ.get("GRADLE_BIN", "/opt/gradle/bin/gradle"),
        "GRADLE_CACHE_TEMPLATE": os.environ.get("GRADLE_CACHE_TEMPLATE", "/opt/gradle-cache-template"),
    }
    result = vs.run_cmd([str(SCRIPTS / "build-offline.sh")], env=env, check=False)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert (APP / "api/build/libs/api.jar").is_file()
    assert Path("/app/release-mirror/build/libs/release-mirror.jar").is_file()


def test_authoritative_policy_is_recovered_from_git_history():
    """Recovered policy version and commit must match the manual-authorized 2026.1 candidate."""
    recovery = subprocess.run(
        [
            "python3",
            "-c",
            """
import pathlib, subprocess, re
from datetime import datetime, timezone
repo=pathlib.Path('/app/pkg')
ws=datetime(2026,1,5,tzinfo=timezone.utc); we=datetime(2026,3,1,23,59,59,tzinfo=timezone.utc)
approvers={'alice@example.com','bob@example.com'}
def git(*a):
    return subprocess.check_output(['git',*a],cwd=repo,text=True,stderr=subprocess.STDOUT)
commits=set(git('log','--all','--format=%H','--','config/signing-policy.yaml').split())
for line in git('fsck','--unreachable','--no-reflogs').splitlines():
    if line.startswith('unreachable commit '): commits.add(line.split()[-1])
auth=[]
for cid in commits:
    try: yaml=git('show',f'{cid}:config/signing-policy.yaml')
    except Exception: continue
    if '2026.1' not in yaml.split('policy_version',1)[-1][:40]: continue
    meta=git('log','-1','--format=%cI%n%B',cid); ds,_,body=meta.partition('\\n')
    ts=datetime.fromisoformat(ds.replace('Z','+00:00'))
    if ts<ws or ts>we: continue
    m=re.search(r'(?im)^Approved-By:\\s*(\\S+)',body)
    if m and m.group(1).lower() in approvers: auth.append(cid)
assert len(auth)==1
print(auth[0])
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    expected = recovery.stdout.strip()
    policy_path = APP / "config" / "signing-policy.yaml"
    assert policy_path.is_file(), "policy file must be restored for signing"
    text = policy_path.read_text()
    assert 'policy_version: "2026.1"' in text or "policy_version: 2026.1" in text
    # Manifest produced by generate path should bind the commit when present.
    if (OUTPUT / "signing-manifest.json").is_file():
        manifest = json.loads((OUTPUT / "signing-manifest.json").read_text())
        assert manifest["policy_commit_id"] == expected


def test_equivalent_directed_and_undirected_digests():
    """Semantically equivalent graphs must share digests; parallel edges stay distinct."""
    base = {
        "graph_id": "g1",
        "graph_type": "undirected",
        "nodes": [{"id": "n1"}, {"id": "n2"}],
        "edges": [
            {"source": "n1", "target": "n2", "kind": "data", "weight": "1.50", "attributes": {"lane": "a"}},
            {"source": "n2", "target": "n1", "kind": "data", "weight": "1.5", "attributes": {"lane": "a"}},
        ],
    }
    permuted = {
        "graph_type": "undirected",
        "graph_id": "g1",
        "nodes": [{"id": "n2"}, {"id": "n1"}],
        "edges": [
            {"source": "n2", "target": "n1", "kind": "data", "weight": "01.5", "attributes": {"lane": "a"}},
        ],
        "layout": {"x": 1},
    }
    assert vs.graph_digest(base) == vs.graph_digest(permuted)

    parallel = {
        "graph_id": "g1",
        "graph_type": "directed",
        "nodes": [{"id": "n1"}, {"id": "n2"}],
        "edges": [
            {"source": "n1", "target": "n2", "kind": "data", "weight": "1.0"},
            {"source": "n1", "target": "n2", "kind": "control", "weight": "1.0"},
        ],
    }
    collapsed = {
        "graph_id": "g1",
        "graph_type": "directed",
        "nodes": [{"id": "n1"}, {"id": "n2"}],
        "edges": [{"source": "n1", "target": "n2", "kind": "data", "weight": "1.0"}],
    }
    assert vs.graph_digest(parallel) != vs.graph_digest(collapsed)


def test_release_fetch_verifies_sha256_on_every_use(tmp_path):
    """Cached tarball must be rehashed; mutated bytes must fail closed."""
    cache = tmp_path / "cache"
    cache.mkdir()
    src = Path("/data/mlflow-release/mlflow-2.16.2.tar.gz")
    cached = cache / "mlflow-2.16.2.tar.gz"
    shutil.copy2(src, cached)
    env = {
        "MLFLOW_RELEASE_URL": "http://127.0.0.1:18081/releases/mlflow-2.16.2.tar.gz",
        "MLFLOW_RELEASE_SHA256_FILE": "/data/mlflow-release/mlflow-2.16.2.sha256",
        "MLFLOW_RELEASE_CACHE": str(cache),
    }
    # Ensure mirror is up
    vs.run_cmd([str(SCRIPTS / "start-release-mirror.sh")], check=False)
    ok = vs.run_cmd([str(SCRIPTS / "fetch-mlflow-release.sh")], env=env, check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    cached.write_bytes(cached.read_bytes() + b"\n")
    bad = vs.run_cmd([str(SCRIPTS / "fetch-mlflow-release.sh")], env=env, check=False)
    assert bad.returncode != 0


def test_release_fetch_rejects_external_redirect(tmp_path):
    """Redirects outside the configured mirror origin must be rejected."""
    vs.run_cmd([str(SCRIPTS / "start-release-mirror.sh")], check=False)
    cache = tmp_path / "redir-cache"
    cache.mkdir()
    env = {
        "MLFLOW_RELEASE_URL": "http://127.0.0.1:18081/redirect-external",
        "MLFLOW_RELEASE_SHA256_FILE": "/data/mlflow-release/mlflow-2.16.2.sha256",
        "MLFLOW_RELEASE_CACHE": str(cache),
    }
    result = vs.run_cmd([str(SCRIPTS / "fetch-mlflow-release.sh")], env=env, check=False)
    assert result.returncode != 0


def test_callback_replay_and_terminal_regression():
    """Exact replay is idempotent; conflicting replay and terminal regression are rejected."""
    import urllib.error
    import urllib.request

    vs.run_cmd([str(SCRIPTS / "start-release-mirror.sh")], check=False)
    vs.run_cmd([str(SCRIPTS / "fetch-mlflow-release.sh")], check=False)
    vs.run_cmd([str(SCRIPTS / "start-pkg.sh")], check=False)
    vs.wait_http("http://127.0.0.1:18082/health")

    graph = json.loads((Path("/data/runs/visible-run-a/graph.json")).read_text())
    digest = vs.graph_digest(graph)
    run = json.loads((Path("/data/runs/visible-run-a/run.json")).read_text())
    # Dedicated run_id so this test does not poison visible-run-a for generate-signing-manifest.
    replay_run_id = "callback-replay-run"

    def post(payload: dict):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18082/v1/callbacks",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw": body}
            return exc.code, parsed

    pending = {
        "event_id": "evt-test-001",
        "run_id": replay_run_id,
        "experiment_id": run["experiment_id"],
        "graph_digest": digest,
        "policy_version": "2026.1",
        "schema_version": "2.16.2",
        "status": "PENDING",
        "occurred_at": "2026-01-10T11:00:01Z",
        "metrics": {"queue_depth": 0},
    }
    running = dict(pending)
    running.update({"event_id": "evt-test-002", "status": "RUNNING", "occurred_at": "2026-01-10T11:05:00Z", "metrics": {"step": 1}})
    finished = dict(running)
    finished.update(
        {
            "event_id": "evt-test-003",
            "status": "FINISHED",
            "occurred_at": "2026-01-10T11:30:00Z",
            "metrics": {"accuracy": 0.91},
            "artifact_digest": "a" * 64,
        }
    )

    status, _ = post(pending)
    assert status == 200
    status, _ = post(running)
    assert status == 200
    status, _finished_body = post(finished)
    assert status == 200

    # exact replay
    status, body2 = post(finished)
    assert status == 200
    assert body2.get("accepted") is True

    # conflicting replay
    conflict = dict(finished)
    conflict["metrics"] = {"accuracy": 0.5}
    status, _conflict_body = post(conflict)
    assert status == 409

    # terminal regression
    regress = dict(finished)
    regress["event_id"] = "evt-test-004"
    regress["status"] = "RUNNING"
    del regress["artifact_digest"]
    status, _regress_body = post(regress)
    assert status in (400, 409)


def test_identity_binds_experiment_and_graph():
    """Callbacks with wrong experiment_id or graph_digest must be rejected."""
    import urllib.error
    import urllib.request

    vs.ensure_fresh_signer()
    graph = json.loads((Path("/data/runs/visible-run-a/graph.json")).read_text())
    digest = vs.graph_digest(graph)

    good = {
        "event_id": "evt-id-1",
        "run_id": "identity-run",
        "experiment_id": "exp-1",
        "graph_digest": digest,
        "policy_version": "2026.1",
        "schema_version": "2.16.2",
        "status": "RUNNING",
        "occurred_at": "2026-01-10T11:00:01Z",
        "metrics": {"step": 0},
    }
    data = json.dumps(good).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:18082/v1/callbacks",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200

    bad = dict(good)
    bad["event_id"] = "evt-id-2"
    bad["experiment_id"] = "exp-other"
    req = urllib.request.Request(
        "http://127.0.0.1:18082/v1/callbacks",
        data=json.dumps(bad).encode(),
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400


def test_visible_workflow_writes_schema_valid_outputs():
    """generate-signing-manifest.sh must emit attestation + schema-valid manifest."""
    if OUTPUT.exists():
        for path in OUTPUT.iterdir():
            if path.is_file():
                path.unlink()
    vs.run_cmd([str(SCRIPTS / "generate-signing-manifest.sh"), "/data/runs/visible-run-a"], check=True)
    att_path = OUTPUT / "run-attestation.json"
    man_path = OUTPUT / "signing-manifest.json"
    assert att_path.is_file()
    assert man_path.is_file()
    attestation = json.loads(att_path.read_text())
    manifest = json.loads(man_path.read_text())
    for key in (
        "policy_commit_id",
        "policy_digest",
        "mlflow_tarball_sha256",
        "callback_schema_sha256",
        "graph_digest",
        "run_digest",
        "terminal_callback_digest",
        "signing_key_id",
        "signature",
        "attestation_schema_version",
    ):
        assert key in attestation
    assert "generatedAt" not in attestation
    assert "mlflow_cache_path" not in attestation
    schema = json.loads(MANIFEST_SCHEMA.read_text())
    Draft7Validator(schema).validate(manifest)
    assert manifest["policy_commit_id"] == attestation["policy_commit_id"]
    assert manifest["graph_digest"] == attestation["graph_digest"]


def test_equivalent_inputs_produce_byte_identical_outputs(tmp_path):
    """Re-running an equivalent signing workflow must be byte-identical."""
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    out_a.mkdir()
    out_b.mkdir()
    env_a = {"GRAPHRUN_OUTPUT": str(out_a)}
    env_b = {"GRAPHRUN_OUTPUT": str(out_b)}
    vs.run_cmd([str(SCRIPTS / "generate-signing-manifest.sh"), "/data/runs/visible-run-a"], env=env_a, check=True)
    vs.run_cmd([str(SCRIPTS / "generate-signing-manifest.sh"), "/data/runs/visible-run-b"], env=env_b, check=False)
    # visible-run-b is graph-equivalent but different run_id; compare graph digests instead when both succeed.
    att_a = json.loads((out_a / "run-attestation.json").read_text())
    graph_a = json.loads(Path("/data/runs/visible-run-a/graph.json").read_text())
    graph_b = json.loads(Path("/data/runs/visible-run-b/graph.json").read_text())
    assert vs.graph_digest(graph_a) == vs.graph_digest(graph_b)
    assert att_a["graph_digest"] == vs.graph_digest(graph_a)
    # same run twice
    out_c = tmp_path / "c"
    out_c.mkdir()
    vs.run_cmd(
        [str(SCRIPTS / "generate-signing-manifest.sh"), "/data/runs/visible-run-a"],
        env={"GRAPHRUN_OUTPUT": str(out_c)},
        check=True,
    )
    assert (out_a / "run-attestation.json").read_bytes() == (out_c / "run-attestation.json").read_bytes()


def test_service_and_mirror_bind_loopback_by_default():
    """Health endpoints must be reachable on documented loopback ports."""
    vs.run_cmd([str(SCRIPTS / "start-release-mirror.sh")], check=False)
    vs.run_cmd([str(SCRIPTS / "start-pkg.sh")], check=False)
    vs.wait_http("http://127.0.0.1:18081/health")
    vs.wait_http("http://127.0.0.1:18082/health")


def test_logs_do_not_expose_private_keys_or_callback_bodies():
    """Service logs must avoid private key bytes, signatures, and raw callback bodies."""
    import urllib.request

    log_path = Path("/tmp/graphrun-signer/graph-run-signer.log")
    vs.ensure_fresh_signer(clear_log=True)
    graph = json.loads((Path("/data/runs/visible-run-a/graph.json")).read_text())
    digest = vs.graph_digest(graph)
    probe = {
        "event_id": "evt-log-probe-1",
        "run_id": "log-probe-run",
        "experiment_id": "exp-log-probe",
        "graph_digest": digest,
        "policy_version": "2026.1",
        "schema_version": "2.16.2",
        "status": "RUNNING",
        "occurred_at": "2026-01-10T11:00:01Z",
        "metrics": {"step": 0},
    }
    req = urllib.request.Request(
        "http://127.0.0.1:18082/v1/callbacks",
        data=json.dumps(probe).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
    assert log_path.is_file(), "signer log not present after probe"
    text = log_path.read_text(errors="ignore")
    assert "BEGIN PRIVATE KEY" not in text
    for key in Path("/data/keys").glob("*.pk8"):
        assert key.read_bytes().hex() not in text
    assert "received callback body=" not in text

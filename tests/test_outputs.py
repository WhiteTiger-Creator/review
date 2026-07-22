"""Behavioral checks for the resolved promotion plan."""

import hashlib
import json
import os
from pathlib import Path
from time import sleep
from urllib.request import Request, urlopen


APP = Path("/app/app")
PLAN = Path("/app/promotion-plan.json")
AUTHORITY_URL = "https://huggingface.co/api/models/google-bert/bert-base-uncased"


def authority_id():
    """Read the stable model identity from the live registry authority with bounded retries."""
    request = Request(AUTHORITY_URL, headers={"User-Agent": "promotion-verifier/1"})
    last_error = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read())
            assert payload.get("id"), "The live authority must return a nonempty model id"
            return payload["id"]
        except (OSError, ValueError, AssertionError) as error:
            last_error = error
            if attempt < 2:
                sleep(attempt + 1)
    raise AssertionError("The live authority did not return a usable model id") from last_error


def load_inputs():
    """Load the registry, requests, and stage policies used by the estate."""
    def read(relative):
        return json.loads((APP / relative).read_text())

    return (
        read("registry/profiles.json")["profiles"],
        read("requests/requests.json")["requests"],
        read("policies/stages.json")["stages"],
    )


def expected_decisions():
    """Recompute every decision and its precedence independently of the solution."""
    profiles, requests, stages = load_inputs()
    authority = authority_id()
    by_id = {p["id"]: p for p in profiles}
    decisions = []
    for request in requests:
        decision = {
            "request_id": request["request_id"],
            "profile_id": "",
            "stage": "none",
            "effective_context": 0,
            "effective_batch": 0,
            "quantization": "",
            "decision": "rejected",
            "reason": "",
        }
        profile = by_id.get(request["profile_id"])
        if profile is None:
            decision["reason"] = "profile-missing"
        elif profile["authority_model"] != authority:
            decision["reason"] = "registry-missing"
        elif profile["status"] != "active" or profile["retired"]:
            decision["reason"] = "inactive-profile"
        elif profile["family"] != request["family"]:
            decision["reason"] = "family-mismatch"
        elif request["target_stage"] not in stages:
            decision["reason"] = "stage-unknown"
        else:
            policy = stages[request["target_stage"]]
            decision["effective_context"] = (
                profile["context_limit"] - request["context_reserve"]
            )
            decision["effective_batch"] = min(
                profile["batch_limit"], request["batch"]
            )
            if decision["effective_context"] < policy["min_context"]:
                decision["reason"] = "context-incompatible"
            elif decision["effective_batch"] > policy["max_batch"]:
                decision["reason"] = "batch-incompatible"
            elif profile["quantization"] not in policy["allowed_quantization"]:
                decision["reason"] = "quantization-incompatible"
            else:
                decision.update(
                    profile_id=profile["id"],
                    stage=request["target_stage"],
                    quantization=profile["quantization"],
                    decision="promoted",
                    reason="promoted",
                )
        decisions.append(decision)
    return decisions


def load_plan():
    """Read the submitted plan and fail clearly when it is absent or invalid JSON."""
    assert PLAN.exists(), "promotion-plan.json was not created"
    return json.loads(PLAN.read_text())


def test_plan_schema_and_key_order():
    """Verify the top-level schema, source, and exact top-level key order."""
    plan = load_plan()
    assert list(plan) == ["schema", "decisions", "source", "digest"]
    assert plan["schema"] == "model-promotion/v3"
    assert plan["source"] == authority_id()


def test_decisions_match_registry_authority_and_precedence():
    """Verify one ordered decision per request, including registry-missing precedence."""
    plan = load_plan()
    assert plan["decisions"] == expected_decisions()
    assert any(d["reason"] == "registry-missing" for d in plan["decisions"])


def test_decision_object_key_order():
    """Verify every decision uses the contract's exact field order."""
    plan = load_plan()
    keys = [
        "request_id", "profile_id", "stage", "effective_context",
        "effective_batch", "quantization", "decision", "reason",
    ]
    assert all(list(decision) == keys for decision in plan["decisions"])


def test_digest_covers_canonical_plan_without_digest():
    """Verify the lowercase SHA256 digest covers only the ordered core object."""
    plan = load_plan()
    core = {
        "schema": plan["schema"],
        "decisions": plan["decisions"],
        "source": plan["source"],
    }
    canonical = json.dumps(core, separators=(",", ":"), ensure_ascii=False)
    assert plan["digest"] == hashlib.sha256(canonical.encode()).hexdigest()


def test_rerunnable_entrypoint_uses_configured_authority(monkeypatch, tmp_path):
    """Verify the documented rerunnable entrypoint honors a controlled authority URL."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from subprocess import run
    import threading

    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            payload = json.dumps({"id": load_inputs()[0][0]["authority_model"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        env = {"PATH": os.environ.get("PATH", ""), "REGISTRY_URL": f"http://127.0.0.1:{server.server_port}"}
        result = run(["/app/solve.sh"], cwd="/app", env={**os.environ, **env}, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert len(calls) >= len(load_inputs()[1])
    finally:
        server.shutdown()

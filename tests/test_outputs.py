"""Black-box verifier for the authgw security-fix task.

Builds and starts /app/cmd/authgw from whatever source is on disk when the
verifier runs (i.e. the agent's current, hopefully-patched, code), then
drives it purely over HTTP the way an external caller would. Nothing here
inspects source code or implementation details.
"""

import base64
import hashlib
import hmac
import json
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

APP_DIR = Path("/app")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "CorrectHorseBattery9"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "hunter2hunter2"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _request(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}"), resp.headers
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode() or "{}")
        except json.JSONDecodeError:
            payload = {}
        return exc.code, payload, exc.headers


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


# The key an attacker recovers by running `strings` (or a disassembler)
# against the authgw-signd helper binary shipped at /app/bin/authgw-signd
# -- it's compiled in as a literal, so it survives symbol stripping.
RECOVERED_SIGND_KEY = b"authgw-signd-secret-4Kp9XvQ7RtmZs2"


def _forge_hs256_admin_token(hmac_key: bytes) -> str:
    """Forge an HS256 admin session token using a recovered HMAC key,
    without ever holding a legitimate admin session."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "uid": 1,
        "username": "admin",
        "role": "admin",
        "iss": "authgw",
        "exp": now + 3600,
        "iat": now,
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    sig = hmac.new(hmac_key, signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


# A UNION-based injection that survives a case-sensitive keyword blocklist
# (lowercase keywords, "/**/" in place of spaces) and balances its own
# quotes so it needs no trailing comment to swallow the query template's
# closing quote.
SQLI_REMEMBER_TOKEN = (
    "x'/**/union/**/select/**/id,'admin'/**/from/**/users/**/where/**/username='admin"
)

# A second bypass using a different technique: each blocked keyword is
# embedded twice, overlapping, so a single non-recursive removal pass
# strips the inner copy and leaves the outer fragments concatenated back
# into the keyword (e.g. "UNIUNIONON" -> remove "UNION" -> "UNI"+"ON" ->
# "UNION"). This defeats a blocklist made case-insensitive but still
# single-pass, so it isn't satisfied by patching the blocklist alone.
SQLI_DOUBLE_INJECTION_TOKEN = (
    "x'/**/UNIUNIONON/**/SELSELECTECT/**/id,'admin'/**/FROM/**/users/**/WHERE/**/username='admin"
)


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    """Build the current /app source and run it as a fresh subprocess."""
    build_dir = tmp_path_factory.mktemp("authgw-build")
    binary = build_dir / "authgw"

    build = subprocess.run(
        ["go", "build", "-o", str(binary), "./cmd/authgw"],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert build.returncode == 0, (
        "go build ./cmd/authgw failed -- the patched source must still compile.\n"
        f"stdout:\n{build.stdout}\nstderr:\n{build.stderr}"
    )

    db_path = build_dir / "authgw.db"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    proc = subprocess.Popen(
        [str(binary)],
        cwd=APP_DIR,
        env={"AUTHGW_DB_PATH": str(db_path), "PORT": str(port), "PATH": "/usr/bin:/bin"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.time() + 15
    healthy = False
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        try:
            status, _, _ = _request("GET", f"{base_url}/healthz")
            if status == 200:
                healthy = True
                break
        except OSError:
            pass
        time.sleep(0.25)

    if not healthy:
        proc.kill()
        out = proc.stdout.read() if proc.stdout else ""
        pytest.fail(f"authgw server never became healthy on {base_url}.\noutput:\n{out}")

    yield base_url

    proc.kill()
    proc.wait(timeout=10)


def _register(server, username, password):
    return _request(
        "POST", f"{server}/auth/register", {"username": username, "password": password}
    )


def _login(server, username, password, remember=False):
    return _request(
        "POST",
        f"{server}/auth/login",
        {"username": username, "password": password, "remember": remember},
    )


def _unique_username(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


class TestLegitimateFlowsStillWork:
    """The fix must not come at the cost of breaking real functionality."""

    def test_register_then_login(self, server):
        """A freshly registered user can log in and receive a session token."""
        username = _unique_username("alice")
        status, body, _ = _register(server, username, "correcthorsebattery")
        assert status == 201, body

        status, body, _ = _login(server, username, "correcthorsebattery")
        assert status == 200, body
        assert body.get("token")

    def test_login_then_profile(self, server):
        """A logged-in user's bearer token grants access to their own profile."""
        username = _unique_username("bob")
        status, _, _ = _register(server, username, "correcthorsebattery")
        assert status == 201

        status, login_body, _ = _login(server, username, "correcthorsebattery")
        assert status == 200

        status, profile, _ = _request(
            "GET",
            f"{server}/api/profile",
            headers={"Authorization": f"Bearer {login_body['token']}"},
        )
        assert status == 200
        assert profile == {"username": username, "role": "user"}

    def test_wrong_password_rejected(self, server):
        """Login with an incorrect password returns 401, not a token."""
        username = _unique_username("carol")
        status, _, _ = _register(server, username, "correcthorsebattery")
        assert status == 201

        status, body, _ = _login(server, username, "not-the-right-password")
        assert status == 401
        assert "token" not in body

    def test_short_credentials_rejected(self, server):
        """Registration enforces the documented minimum lengths."""
        status, _, _ = _register(server, "ab", "short")
        assert status == 400

    def test_admin_can_list_users(self, server):
        """The seeded admin account can still reach /admin/users."""
        status, login_body, _ = _login(server, ADMIN_USERNAME, ADMIN_PASSWORD)
        assert status == 200

        status, body, _ = _request(
            "GET",
            f"{server}/admin/users",
            headers={"Authorization": f"Bearer {login_body['token']}"},
        )
        assert status == 200
        usernames = {u["username"] for u in body["users"]}
        assert ADMIN_USERNAME in usernames
        assert DEMO_USERNAME in usernames

    def test_non_admin_cannot_list_users(self, server):
        """A regular user's token must not grant access to /admin/users."""
        status, login_body, _ = _login(server, DEMO_USERNAME, DEMO_PASSWORD)
        assert status == 200

        status, _, _ = _request(
            "GET",
            f"{server}/admin/users",
            headers={"Authorization": f"Bearer {login_body['token']}"},
        )
        assert status == 403

    def test_remember_me_cookie_round_trip(self, server):
        """A remember=true login's cookie authenticates later requests with
        no Authorization header at all."""
        status, login_body, headers = _login(server, DEMO_USERNAME, DEMO_PASSWORD, remember=True)
        assert status == 200
        remember_token = login_body.get("remember_token")
        assert remember_token

        status, profile, _ = _request(
            "GET", f"{server}/api/profile", headers={"Cookie": f"remember_token={remember_token}"}
        )
        assert status == 200
        assert profile == {"username": DEMO_USERNAME, "role": "user"}

    def test_jwks_endpoint_shape(self, server):
        """/.well-known/jwks.json publishes a standard single-key RSA JWK set."""
        status, body, _ = _request("GET", f"{server}/.well-known/jwks.json")
        assert status == 200
        assert "keys" in body and len(body["keys"]) == 1
        key = body["keys"][0]
        assert key["kty"] == "RSA"
        assert key["alg"] == "RS256"
        assert "n" in key and "e" in key

    def test_healthz_reports_instance_id(self, server):
        """/healthz still reports status plus a per-replica instance_id."""
        status, body, _ = _request("GET", f"{server}/healthz")
        assert status == 200
        assert body.get("status") == "ok"
        assert body.get("instance_id")

    def test_admin_audit_log_records_logins(self, server):
        """Successful and failed logins are recorded, and only an admin can
        read the audit log back."""
        username = _unique_username("dave")
        _register(server, username, "correcthorsebattery")
        _login(server, username, "correcthorsebattery")
        _login(server, username, "wrong-password")

        status, login_body, _ = _login(server, ADMIN_USERNAME, ADMIN_PASSWORD)
        assert status == 200
        status, body, _ = _request(
            "GET",
            f"{server}/admin/audit-log",
            headers={"Authorization": f"Bearer {login_body['token']}"},
        )
        assert status == 200
        events = {(e["Event"], e["Username"]) for e in body["entries"]}
        assert ("login_success", username) in events
        assert ("login_failure", username) in events

        status, demo_login, _ = _login(server, DEMO_USERNAME, DEMO_PASSWORD)
        assert status == 200
        status, _, _ = _request(
            "GET",
            f"{server}/admin/audit-log",
            headers={"Authorization": f"Bearer {demo_login['token']}"},
        )
        assert status == 403

    def test_admin_service_token_flow(self, server):
        """Admins can still mint RS256 service tokens, and non-admins cannot."""
        status, login_body, _ = _login(server, ADMIN_USERNAME, ADMIN_PASSWORD)
        assert status == 200

        status, body, _ = _request(
            "POST",
            f"{server}/admin/service-tokens",
            headers={"Authorization": f"Bearer {login_body['token']}"},
        )
        assert status == 200
        assert body.get("service_token")

        status, demo_login, _ = _login(server, DEMO_USERNAME, DEMO_PASSWORD)
        assert status == 200
        status, _, _ = _request(
            "POST",
            f"{server}/admin/service-tokens",
            headers={"Authorization": f"Bearer {demo_login['token']}"},
        )
        assert status == 403


class TestVulnerabilitiesAreFixed:
    """The two privilege-escalation paths must no longer work."""

    def test_forged_admin_token_with_recovered_key_is_rejected(self, server):
        """A token carrying role=admin, forged with the HMAC key recovered
        from the shipped authgw-signd helper binary, must not be accepted
        as a valid session -- regardless of whether the fixed code still
        uses that binary at all."""
        forged = _forge_hs256_admin_token(RECOVERED_SIGND_KEY)
        status, _, _ = _request(
            "GET", f"{server}/admin/users", headers={"Authorization": f"Bearer {forged}"}
        )
        assert status in (401, 403), (
            "a forged admin token signed with the recovered authgw-signd key "
            f"was accepted (status {status}); the session token is still "
            "verifiable with that key"
        )

    def test_sql_injection_remember_token_is_rejected(self, server):
        """A remember_token cookie containing a UNION-based SQL injection
        payload must not resolve to the admin account."""
        status, _, _ = _request(
            "GET",
            f"{server}/admin/users",
            headers={"Cookie": f"remember_token={SQLI_REMEMBER_TOKEN}"},
        )
        assert status in (401, 403), (
            f"a SQL-injection remember_token payload was accepted (status {status}); "
            "the injection in the remember-me lookup is still present"
        )

    def test_sql_injection_double_keyword_bypass_is_rejected(self, server):
        """A second, structurally different SQL injection payload (doubled,
        overlapping keywords that reassemble after a single-pass strip)
        must also be rejected -- so patching the keyword blocklist instead
        of parameterizing the query doesn't count as a fix."""
        status, _, _ = _request(
            "GET",
            f"{server}/admin/users",
            headers={"Cookie": f"remember_token={SQLI_DOUBLE_INJECTION_TOKEN}"},
        )
        assert status in (401, 403), (
            f"a double-keyword SQL-injection bypass was accepted (status {status}); "
            "the remember-me lookup is still vulnerable to injection"
        )

    def test_garbage_remember_token_fails_cleanly(self, server):
        """An unrecognized remember_token must be rejected without a server
        error, showing the fix didn't just start crashing on odd input."""
        status, _, _ = _request(
            "GET",
            f"{server}/api/profile",
            headers={"Cookie": "remember_token=not-a-real-token-0000"},
        )
        assert status == 401

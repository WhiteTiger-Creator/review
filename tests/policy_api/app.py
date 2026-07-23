"""Verifier-controlled localhost Flask policy API."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from policy_api.fixtures import (
    PROD_FRAGS,
    PROD_MANIFEST,
    PRODUCTION_REVISION,
    STAGING_REVISION,
    STG_FRAGS,
    STG_MANIFEST,
    fragment_response,
)


class RequestLog:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def record(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        with self._lock:
            self.entries.append({"method": method, "path": path, "query": query})

    def reset(self) -> None:
        with self._lock:
            self.entries.clear()


REQUEST_LOG = RequestLog()
SCENARIO: dict[str, Any] = {"mode": "valid"}


class PolicyHandler(BaseHTTPRequestHandler):
    server_version = "PgPolicyAPI/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _query(self) -> dict[str, list[str]]:
        return parse_qs(urlparse(self.path).query)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = self._query()
        REQUEST_LOG.record("GET", path, query)

        mode = SCENARIO.get("mode", "valid")
        if mode == "connection_refused":
            self.close_connection = True
            return

        if mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1/other")
            self.end_headers()
            return

        if path == "/v1/policy/manifest":
            self._handle_manifest(query, mode)
            return

        for fid in ("identity", "database", "access"):
            if path == f"/v1/policy/fragments/{fid}":
                self._handle_fragment(fid, query, mode)
                return

        self.send_response(404)
        self.end_headers()

    def _handle_manifest(self, query: dict[str, list[str]], mode: str) -> None:
        env = (query.get("environment") or [""])[0]
        if mode == "manifest_500":
            self.send_response(500)
            self.end_headers()
            return
        if mode == "manifest_404":
            self.send_response(404)
            self.end_headers()
            return
        if mode == "manifest_bad_content_type":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"not json")
            return
        if mode == "manifest_malformed":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{broken")
            return
        if mode == "manifest_env_mismatch":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "policy_revision": PRODUCTION_REVISION,
                        "environment": "development",
                        "fragments": [],
                    },
                    separators=(",", ":"),
                ).encode()
            )
            return
        if mode == "manifest_duplicate_fragment":
            body = json.dumps(
                {
                    "policy_revision": PRODUCTION_REVISION,
                    "environment": "production",
                    "fragments": [
                        {"fragment_id": "identity", "body_sha256": "a" * 64},
                        {"fragment_id": "identity", "body_sha256": "b" * 64},
                        {"fragment_id": "access", "body_sha256": "c" * 64},
                    ],
                },
                separators=(",", ":"),
            ).encode()
            self._json_response(200, body)
            return
        if mode == "manifest_unknown_fragment":
            body = json.dumps(
                {
                    "policy_revision": PRODUCTION_REVISION,
                    "environment": "production",
                    "fragments": [
                        {"fragment_id": "identity", "body_sha256": "a" * 64},
                        {"fragment_id": "database", "body_sha256": "b" * 64},
                        {"fragment_id": "unknown", "body_sha256": "c" * 64},
                    ],
                },
                separators=(",", ":"),
            ).encode()
            self._json_response(200, body)
            return
        if mode == "manifest_missing_fragment":
            body = json.dumps(
                {
                    "policy_revision": PRODUCTION_REVISION,
                    "environment": "production",
                    "fragments": [
                        {
                            "fragment_id": "identity",
                            "body_sha256": PROD_FRAGS["identity"][1],
                        },
                        {
                            "fragment_id": "database",
                            "body_sha256": PROD_FRAGS["database"][1],
                        },
                    ],
                },
                separators=(",", ":"),
            ).encode()
            self._json_response(200, body)
            return

        if env == "production":
            self._json_response(200, PROD_MANIFEST)
        elif env == "staging":
            self._json_response(200, STG_MANIFEST)
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_fragment(
        self, fid: str, query: dict[str, list[str]], mode: str
    ) -> None:
        env = (query.get("environment") or [""])[0]
        revision = (query.get("revision") or [""])[0]
        if mode == "fragment_500":
            self.send_response(500)
            self.end_headers()
            return
        if mode == "fragment_bad_content_type":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html></html>")
            return
        if mode == "fragment_malformed":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{")
            return
        if mode == "fragment_digest_mismatch":
            body, _ = PROD_FRAGS[fid]
            self._json_response(200, body[:-1] + (b"}" if body[-1:] == b"}" else b""))
            return
        if mode == "fragment_revision_mismatch":
            doc = {
                "required_roles": [],
                "role_constraints": [],
                "required_memberships": [],
                "forbidden_memberships": [],
            }
            body, _ = fragment_response(env, "wrong-revision", fid, doc)
            self._json_response(200, body)
            return
        if mode == "fragment_env_mismatch":
            doc = {
                "required_roles": [],
                "role_constraints": [],
                "required_memberships": [],
                "forbidden_memberships": [],
            }
            body, _ = fragment_response("development", revision, fid, doc)
            self._json_response(200, body)
            return
        if mode == "fragment_id_mismatch":
            if env == "production":
                body = PROD_FRAGS[fid][0]
                obj = json.loads(body.decode())
                obj["fragment_id"] = "wrong"
                self._json_response(
                    200, json.dumps(obj, separators=(",", ":")).encode()
                )
                return

        frags = (
            PROD_FRAGS
            if env == "production"
            else STG_FRAGS
            if env == "staging"
            else None
        )
        expected_rev = PRODUCTION_REVISION if env == "production" else STAGING_REVISION
        if not frags or revision != expected_rev:
            self.send_response(404)
            self.end_headers()
            return
        self._json_response(200, frags[fid][0])

    def _json_response(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_server(
    host: str = "127.0.0.1", port: int = 0
) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer((host, port), PolicyHandler)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://{host}:{actual_port}"


def set_scenario(mode: str) -> None:
    SCENARIO["mode"] = mode


def reset_scenario() -> None:
    SCENARIO["mode"] = "valid"
    REQUEST_LOG.reset()


if __name__ == "__main__":
    srv, url = start_server()
    print(url)
    import time

    time.sleep(3600)

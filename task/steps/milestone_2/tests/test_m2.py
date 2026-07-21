"""Milestone 2 - REST API endpoints, authentication, pagination, body limits, and thread safety."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "http://127.0.0.1:8080"
API_KEY = "tb3_notes_api_secret_2026"


def _json_request(
    method: str,
    path: str,
    body: object | None = None,
    include_auth: bool = True,
) -> tuple[int, dict | list]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers: dict[str, str] = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if include_auth and method in ("POST", "PUT", "DELETE"):
        headers["X-API-Key"] = API_KEY
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw}


def _json_request_with_headers(
    method: str,
    path: str,
    body: object | None = None,
    include_auth: bool = True,
) -> tuple[int, dict | list, dict]:
    """Like _json_request but also returns response headers."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers: dict[str, str] = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if include_auth and method in ("POST", "PUT", "DELETE"):
        headers["X-API-Key"] = API_KEY
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            resp_headers = dict(resp.headers)
            return resp.status, json.loads(raw) if raw else {}, resp_headers
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        resp_headers = dict(exc.headers)
        try:
            return exc.code, json.loads(raw) if raw else {}, resp_headers
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw}, resp_headers


def _assert_json_and_cors_headers(headers: dict, context: str) -> None:
    ct = headers.get("Content-Type", "")
    assert "application/json" in ct, f"{context}: Content-Type missing, got: {ct}"
    cors = headers.get("Access-Control-Allow-Origin", "")
    assert cors == "*", f"{context}: CORS header missing, got: {cors}"


def _create_note(
    title: str = "Test Note", content: str = "Test content"
) -> tuple[int, dict]:
    return _json_request("POST", "/api/notes", {"title": title, "content": content})


# --- Configuration and persistence tests ---



class TestMilestone2:
    def test_api_key_file_exists(self):
        """The API key file must exist at /app/config/api.key."""
        assert os.path.isfile("/app/config/api.key"), "/app/config/api.key not found"
    
    
    def test_api_key_read_from_file(self):
        """Server must authenticate using the key stored in /app/config/api.key."""
        with open("/app/config/api.key") as f:
            file_key = f.read().strip()
        data = json.dumps({"title": "KeyFile Check", "content": "body"}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE}/api/notes",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "X-API-Key": file_key},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                code = resp.status
        except urllib.error.HTTPError as exc:
            code = exc.code
        assert code == 201, f"Key from /app/config/api.key must authenticate, got {code}"
    
    
    def test_database_file_at_expected_path(self):
        """Notes must be persisted in SQLite at /app/data/notes.db."""
        _create_note("DB Path Check", "persistence")
        assert os.path.isfile("/app/data/notes.db"), "Database not found at /app/data/notes.db"
    
    
    # --- CRUD tests ---
    
    
    def test_create_note_returns_201(self):
        """POST /api/notes with valid data must return HTTP 201."""
        code, payload = _create_note("Status Check", "Body")
        assert code == 201, f"Expected 201, got {code}: {payload}"
    
    
    def test_create_note_returns_id_field(self):
        """Created note response must include a numeric id field."""
        code, payload = _create_note("ID Check", "Body")
        assert code == 201
        assert "id" in payload
        assert isinstance(payload["id"], (int, float))
    
    
    def test_create_note_echoes_title_and_content(self):
        """Created note response must echo back the submitted title and content."""
        code, payload = _create_note("Echo Title", "Echo Body")
        assert code == 201
        assert payload["title"] == "Echo Title"
        assert payload["content"] == "Echo Body"
    
    
    def test_create_note_missing_title_returns_400(self):
        """POST /api/notes with an empty title must return HTTP 400."""
        code, _ = _json_request("POST", "/api/notes", {"title": "", "content": "x"})
        assert code == 400
    
    
    def test_create_note_empty_body_returns_400(self):
        """POST /api/notes with empty JSON object must return HTTP 400."""
        code, _ = _json_request("POST", "/api/notes", {})
        assert code == 400
    
    
    def test_get_all_notes_returns_array(self):
        """GET /api/notes must return a JSON array."""
        _create_note("Array Test", "Body")
        code, payload = _json_request("GET", "/api/notes")
        assert code == 200
        assert isinstance(payload, list)
    
    
    def test_get_all_notes_includes_created_note(self):
        """A note created via POST must appear in the list endpoint response."""
        code, created = _create_note("Find Me", "In the List")
        assert code == 201
        _, notes = _json_request("GET", "/api/notes?limit=100")
        target = next(n for n in notes if int(n["id"]) == int(created["id"]))
        assert target["title"] == "Find Me"
        assert target["content"] == "In the List"
    
    
    def test_get_single_note_by_id(self):
        """GET /api/notes/<id> must return the correct note."""
        _, created = _create_note("Single Fetch", "Unique Body")
        note_id = int(created["id"])
        code, payload = _json_request("GET", f"/api/notes/{note_id}")
        assert code == 200
        assert payload["title"] == "Single Fetch"
    
    
    def test_get_nonexistent_note_returns_404(self):
        """GET /api/notes/<id> for a missing note must return HTTP 404."""
        code, payload = _json_request("GET", "/api/notes/99999")
        assert code == 404
        assert payload.get("error") == "not found"
    
    
    def test_update_note_changes_fields(self):
        """PUT /api/notes/<id> must update the note and return updated data."""
        _, created = _create_note("Before Update", "Old content")
        note_id = int(created["id"])
        code, payload = _json_request(
            "PUT", f"/api/notes/{note_id}", {"title": "Updated Name", "content": "New"}
        )
        assert code == 200
        assert isinstance(payload.get("id"), (int, float))
        assert int(payload["id"]) == note_id
        assert payload["title"] == "Updated Name"
        assert payload["content"] == "New"
    
    
    def test_update_note_empty_title_returns_400(self):
        """PUT /api/notes/<id> with an empty title must return HTTP 400."""
        _, created = _create_note("Before", "Body")
        note_id = int(created["id"])
        code, _ = _json_request(
            "PUT", f"/api/notes/{note_id}", {"title": "", "content": "x"}
        )
        assert code == 400
    
    
    def test_update_note_missing_title_returns_400(self):
        """PUT /api/notes/<id> with missing title must return HTTP 400."""
        _, created = _create_note("Before", "Body")
        note_id = int(created["id"])
        code, _ = _json_request("PUT", f"/api/notes/{note_id}", {})
        assert code == 400
    
    
    def test_update_nonexistent_note_returns_404(self):
        """PUT /api/notes/<id> for a missing note must return HTTP 404."""
        code, payload = _json_request(
            "PUT", "/api/notes/99999", {"title": "Ghost", "content": "None"}
        )
        assert code == 404
        assert payload.get("error") == "not found"
    
    
    def test_delete_note_removes_it(self):
        """DELETE /api/notes/<id> must remove the note so GET returns 404."""
        _, created = _create_note("Delete Target", "Gone soon")
        note_id = int(created["id"])
        code, payload = _json_request("DELETE", f"/api/notes/{note_id}")
        assert code == 200
        assert payload.get("status") == "deleted"
        get_code, _ = _json_request("GET", f"/api/notes/{note_id}")
        assert get_code == 404
    
    
    def test_delete_nonexistent_note_returns_404(self):
        """DELETE /api/notes/<id> for a missing note must return HTTP 404."""
        code, payload = _json_request("DELETE", "/api/notes/99999")
        assert code == 404
        assert payload.get("error") == "not found"
    
    
    def test_api_get_response_content_type_is_json(self):
        """GET /api/notes response must include Content-Type: application/json."""
        req = urllib.request.Request(f"{BASE}/api/notes", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            ct = resp.headers.get("Content-Type", "")
        assert "application/json" in ct
    
    
    def test_api_get_response_has_cors_header(self):
        """GET /api/notes response must include Access-Control-Allow-Origin: *."""
        req = urllib.request.Request(f"{BASE}/api/notes", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            cors = resp.headers.get("Access-Control-Allow-Origin", "")
        assert cors == "*"
    
    
    def test_api_options_preflight_returns_cors_allowlist(self):
        """OPTIONS /api/notes must advertise allowed methods and headers for browser CORS."""
        req = urllib.request.Request(f"{BASE}/api/notes", method="OPTIONS")
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status in (200, 204)
            allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
            allow_methods = resp.headers.get("Access-Control-Allow-Methods", "")
            allow_headers = resp.headers.get("Access-Control-Allow-Headers", "")
        assert allow_origin == "*"
        for method in ("GET", "POST", "PUT", "DELETE", "OPTIONS"):
            assert method in allow_methods, (
                f"Access-Control-Allow-Methods must include {method}, got {allow_methods!r}"
            )
        assert "Content-Type" in allow_headers, (
            f"Access-Control-Allow-Headers must allow Content-Type, got {allow_headers!r}"
        )
        assert "X-API-Key" in allow_headers, (
            f"Access-Control-Allow-Headers must allow X-API-Key, got {allow_headers!r}"
        )
    
    
    def test_api_post_response_content_type_and_cors(self):
        """POST /api/notes response must carry Content-Type: application/json and CORS header."""
        code, _, headers = _json_request_with_headers(
            "POST", "/api/notes", {"title": "Headers POST", "content": "check"}
        )
        assert code == 201
        _assert_json_and_cors_headers(headers, "POST /api/notes")
    
    
    def test_api_put_response_content_type_and_cors(self):
        """PUT /api/notes/<id> response must carry Content-Type: application/json and CORS header."""
        _, created = _create_note("Headers PUT", "before")
        note_id = int(created["id"])
        code, _, headers = _json_request_with_headers(
            "PUT", f"/api/notes/{note_id}", {"title": "Headers PUT", "content": "after"}
        )
        assert code == 200
        _assert_json_and_cors_headers(headers, "PUT /api/notes/<id>")
    
    
    def test_api_delete_response_content_type_and_cors(self):
        """DELETE /api/notes/<id> response must carry Content-Type: application/json and CORS header."""
        _, created = _create_note("Headers DEL", "target")
        note_id = int(created["id"])
        code, _, headers = _json_request_with_headers(
            "DELETE", f"/api/notes/{note_id}"
        )
        assert code == 200
        _assert_json_and_cors_headers(headers, "DELETE /api/notes/<id>")
    
    
    def test_api_get_single_response_content_type_and_cors(self):
        """GET /api/notes/<id> response must carry Content-Type: application/json and CORS header."""
        _, created = _create_note("Headers GET1", "single")
        note_id = int(created["id"])
        code, _, headers = _json_request_with_headers("GET", f"/api/notes/{note_id}")
        assert code == 200
        _assert_json_and_cors_headers(headers, "GET /api/notes/<id>")
    
    
    def test_error_responses_have_json_and_cors_headers(self):
        """API error responses (400/401/404/413) must still include JSON Content-Type and CORS headers."""
        cases: list[tuple[str, str, object | None, bool, int]] = [
            ("POST", "/api/notes", {}, True, 400),
            (
                "POST",
                "/api/notes",
                {"title": "No Auth", "content": "Denied"},
                False,
                401,
            ),
            ("GET", "/api/notes/99999", None, True, 404),
            ("POST", "/api/notes", {"title": "Big", "content": "x" * 70000}, True, 413),
        ]
        for method, path, body, include_auth, expected_status in cases:
            code, _, headers = _json_request_with_headers(
                method, path, body=body, include_auth=include_auth
            )
            assert code == expected_status
            _assert_json_and_cors_headers(headers, f"{method} {path} ({expected_status})")
    
    
    # --- Authentication tests ---
    
    
    def test_post_without_api_key_returns_401(self):
        """POST /api/notes without X-API-Key header must return 401."""
        code, _ = _json_request(
            "POST", "/api/notes", {"title": "No Auth", "content": "Fail"},
            include_auth=False,
        )
        assert code == 401, f"Expected 401, got {code}"
    
    
    def test_put_without_api_key_returns_401(self):
        """PUT /api/notes/<id> without X-API-Key header must return 401."""
        _, created = _create_note("Auth Put", "Before")
        note_id = int(created["id"])
        code, _ = _json_request(
            "PUT", f"/api/notes/{note_id}", {"title": "No Auth", "content": "Fail"},
            include_auth=False,
        )
        assert code == 401, f"Expected 401, got {code}"
    
    
    def test_delete_without_api_key_returns_401(self):
        """DELETE /api/notes/<id> without X-API-Key header must return 401."""
        _, created = _create_note("Auth Del", "Target")
        note_id = int(created["id"])
        code, _ = _json_request(
            "DELETE", f"/api/notes/{note_id}", include_auth=False,
        )
        assert code == 401, f"Expected 401, got {code}"
    
    
    def test_wrong_api_key_returns_401(self):
        """POST with an incorrect API key must return 401."""
        data = json.dumps({"title": "Wrong Key", "content": "Fail"}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE}/api/notes",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": "wrong-key-value",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                code = resp.status
        except urllib.error.HTTPError as exc:
            code = exc.code
        assert code == 401, f"Expected 401, got {code}"
    
    
    def test_put_wrong_api_key_returns_401(self):
        """PUT with an incorrect API key must return 401."""
        _, created = _create_note("Put Wrong Key", "target")
        note_id = int(created["id"])
        data = json.dumps({"title": "Hacked", "content": "No"}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE}/api/notes/{note_id}",
            data=data,
            method="PUT",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": "wrong-key-value",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                code = resp.status
        except urllib.error.HTTPError as exc:
            code = exc.code
        assert code == 401, f"Expected 401, got {code}"
    
    
    def test_delete_wrong_api_key_returns_401(self):
        """DELETE with an incorrect API key must return 401."""
        _, created = _create_note("Del Wrong Key", "target")
        note_id = int(created["id"])
        req = urllib.request.Request(
            f"{BASE}/api/notes/{note_id}",
            method="DELETE",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": "wrong-key-value",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                code = resp.status
        except urllib.error.HTTPError as exc:
            code = exc.code
        assert code == 401, f"Expected 401, got {code}"
    
    
    def test_get_without_api_key_succeeds(self):
        """GET /api/notes must succeed without an API key (read is public)."""
        code, _ = _json_request("GET", "/api/notes", include_auth=False)
        assert code == 200
    
    
    def test_get_single_note_without_api_key_succeeds(self):
        """GET /api/notes/<id> must succeed without an API key."""
        _, created = _create_note("Public Read", "Accessible")
        note_id = int(created["id"])
        code, _ = _json_request("GET", f"/api/notes/{note_id}", include_auth=False)
        assert code == 200
    
    
    # --- Pagination tests ---
    
    
    def test_pagination_limit_returns_correct_count(self):
        """GET /api/notes?limit=2 must return at most 2 notes."""
        for i in range(5):
            _create_note(f"Paginate {i}", f"Body {i}")
        code, payload = _json_request("GET", "/api/notes?limit=2")
        assert code == 200
        assert isinstance(payload, list)
        assert len(payload) == 2
    
    
    def test_pagination_offset_skips_notes(self):
        """GET /api/notes?limit=2&offset=2 must skip the first two notes."""
        ids = []
        for i in range(5):
            _, created = _create_note(f"OffsetTest {i}", f"Body {i}")
            ids.append(int(created["id"]))
        code, page1 = _json_request("GET", "/api/notes?limit=2&offset=0")
        assert code == 200
        code, page2 = _json_request("GET", "/api/notes?limit=2&offset=2")
        assert code == 200
        page1_ids = {int(n["id"]) for n in page1}
        page2_ids = {int(n["id"]) for n in page2}
        assert page1_ids.isdisjoint(page2_ids), "Pages must not overlap"
    
    
    def test_pagination_x_total_count_header(self):
        """X-Total-Count must equal the full row count while limit only caps the page."""
        _, notes_before = _json_request("GET", "/api/notes?limit=100")
        before_count = len(notes_before) if isinstance(notes_before, list) else 0
        batch_size = 5
        for i in range(batch_size):
            _create_note(f"CountHdr {i}", f"Body {i}")
        expected_total = before_count + batch_size
        code, payload, headers = _json_request_with_headers(
            "GET", "/api/notes?limit=2"
        )
        assert code == 200
        assert isinstance(payload, list)
        assert len(payload) == 2
        total = headers.get("X-Total-Count")
        assert total is not None, "X-Total-Count header missing"
        assert int(total) == expected_total, (
            f"X-Total-Count must be {expected_total} (all rows before paging), got {total!r}"
        )
    
    
    def test_pagination_default_limit_is_50(self):
        """GET /api/notes without explicit limit must return at most 50 notes (default limit)."""
        for i in range(55):
            _create_note(f"DefLimit {i}", f"Body {i}")
        code, payload = _json_request("GET", "/api/notes")
        assert code == 200
        assert isinstance(payload, list)
        assert len(payload) == 50, f"Default limit should be 50, got {len(payload)} notes"
    
    
    def test_pagination_max_limit_capped_at_100(self):
        """GET /api/notes?limit=999 must cap the limit at 100 when more than 100 rows exist."""
        _, _, headers = _json_request_with_headers("GET", "/api/notes?limit=1")
        total = int(headers.get("X-Total-Count", "0"))
        needed = max(0, 105 - total)
        for i in range(needed):
            code, created = _create_note(f"CapFill {i}", f"body {i}")
            assert code == 201, f"Failed to seed note {i}: {created!r}"
        code, payload = _json_request("GET", "/api/notes?limit=999")
        assert code == 200
        assert isinstance(payload, list)
        assert len(payload) == 100, (
            f"limit=999 must cap at exactly 100 rows, got {len(payload)}"
        )
    
    
    # --- Body size limit tests ---
    
    
    def test_oversized_post_body_returns_413(self):
        """POST with a body exceeding 64KB must return HTTP 413 with a JSON error body."""
        large_body = {"title": "Big", "content": "x" * 70000}
        code, payload = _json_request("POST", "/api/notes", large_body)
        assert code == 413, f"Expected 413, got {code}"
        assert isinstance(payload, dict), "413 response must be a JSON object"
        assert "error" in payload, "413 body must contain an error field"
    
    
    def test_oversized_put_body_returns_413(self):
        """PUT with a body exceeding 64KB must return HTTP 413 with a JSON error body."""
        _, created = _create_note("Small Note", "Normal")
        note_id = int(created["id"])
        large_body = {"title": "Big", "content": "x" * 70000}
        code, payload = _json_request("PUT", f"/api/notes/{note_id}", large_body)
        assert code == 413, f"Expected 413, got {code}"
        assert isinstance(payload, dict), "413 response must be a JSON object"
        assert "error" in payload, "413 body must contain an error field"
    
    
    # --- Concurrent access tests ---
    
    
    def test_concurrent_creates_all_succeed(self):
        """20 concurrent POST requests must all succeed (thread-safe DB)."""
        def create_one(i: int) -> tuple[int, dict]:
            return _json_request(
                "POST", "/api/notes",
                {"title": f"Concurrent {i}", "content": f"Body {i}"},
            )
    
        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(create_one, i) for i in range(20)]
            results = [f.result() for f in as_completed(futures)]
    
        successes = [r for r in results if r[0] == 201]
        assert len(successes) == 20, (
            f"Expected all 20 concurrent creates to succeed, but only {len(successes)} did. "
            f"Status codes: {[r[0] for r in results]}"
        )
    
    
    def test_concurrent_creates_no_data_loss(self):
        """All notes created concurrently must be retrievable afterward."""
        titles = [f"CLoss {i}" for i in range(15)]
    
        def create_one(title: str) -> tuple[int, dict]:
            return _json_request(
                "POST", "/api/notes", {"title": title, "content": "concurrent body"},
            )
    
        with ThreadPoolExecutor(max_workers=15) as pool:
            futures = {pool.submit(create_one, t): t for t in titles}
            created_ids = []
            for future in as_completed(futures):
                code, payload = future.result()
                assert code == 201, f"Create failed: {code}"
                created_ids.append(int(payload["id"]))
    
        for cid in created_ids:
            code, _ = _json_request("GET", f"/api/notes/{cid}")
            assert code == 200, f"Note {cid} was lost after concurrent creation"

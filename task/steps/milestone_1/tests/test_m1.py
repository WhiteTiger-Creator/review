"""Milestone 1 - Server compilation, startup on port 8080, and static file serving."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080"
WWW_DIR = Path("/app/www")


def _get(path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")



class TestMilestone1:
    def test_server_binary_exists(self):
        """The notes_server binary must exist after compilation."""
        assert Path("/app/notes_server").is_file(), (
            "notes_server binary not found at /app/notes_server"
        )

    def test_server_binary_is_elf(self):
        """notes_server must be a compiled ELF binary, not a script stub."""
        result = subprocess.run(
            ["file", "/app/notes_server"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "ELF" in result.stdout, (
            f"notes_server must be a compiled binary; file(1) said: {result.stdout!r}"
        )

    def test_server_responds_on_port_8080(self):
        """Server must be reachable on port 8080 and return a JSON array from GET /api/notes."""
        code, body = _get("/api/notes")
        assert code == 200
        data = json.loads(body)
        assert isinstance(data, list), "GET /api/notes must return a JSON array"
    
    
    def test_root_serves_html_page(self):
        """GET / must serve an HTML page."""
        code, body = _get("/")
        assert code == 200
        expected = (WWW_DIR / "index.html").read_text(encoding="utf-8")
        assert body == expected, "GET / must serve /app/www/index.html verbatim"
    
    
    def test_css_stylesheet_is_served(self):
        """The CSS stylesheet must match /app/www/style.css on disk."""
        code, body = _get("/style.css")
        assert code == 200
        expected = (WWW_DIR / "style.css").read_text(encoding="utf-8")
        assert body == expected, "Response must match /app/www/style.css"

    def test_javascript_file_is_served(self):
        """The JavaScript file must match /app/www/app.js on disk."""
        code, body = _get("/app.js")
        assert code == 200
        expected = (WWW_DIR / "app.js").read_text(encoding="utf-8")
        assert body == expected, "Response must match /app/www/app.js"
    
    
    def test_html_contains_note_form(self):
        """Page must contain a form with id note-form."""
        _, body = _get("/")
        assert 'id="note-form"' in body
    
    
    def test_html_contains_title_input(self):
        """Page must contain an input with id note-title."""
        _, body = _get("/")
        assert 'id="note-title"' in body
    
    
    def test_html_contains_content_textarea(self):
        """Page must contain a textarea with id note-content."""
        _, body = _get("/")
        assert 'id="note-content"' in body
    
    
    def test_html_contains_submit_button(self):
        """Page must contain a submit button with id btn-submit."""
        _, body = _get("/")
        assert 'id="btn-submit"' in body
    
    
    def test_html_contains_notes_list_container(self):
        """Page must contain a notes list container with id notes-list."""
        _, body = _get("/")
        assert 'id="notes-list"' in body
    
    
    def test_nonexistent_static_file_returns_404(self):
        """Requesting a nonexistent static file should return 404."""
        code, _ = _get("/nonexistent.txt")
        assert code == 404
    
    
    def test_path_traversal_blocked(self):
        """Requests containing '..' must be rejected with HTTP 403."""
        code, _ = _get("/../../../etc/passwd")
        assert code == 403, f"Path traversal must return 403, got {code}"
    
    
    def test_path_traversal_encoded_blocked(self):
        """Double-dot traversal via /www/.. must be rejected with HTTP 403."""
        code, _ = _get("/www/../../../etc/shadow")
        assert code == 403, f"Path traversal must return 403, got {code}"
    
    
    def test_path_traversal_percent_encoded_dotdot_blocked(self):
        """Percent-encoded '..' (%2e%2e) must not escape the www directory (403)."""
        code, _ = _get("/%2e%2e/%2e%2e/etc/passwd")
        assert code == 403, f"Encoded path traversal must return 403, got {code}"

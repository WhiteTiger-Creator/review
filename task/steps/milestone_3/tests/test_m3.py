"""Milestone 3 verifier (test_m3.py): frontend JS and end-to-end checks."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

import quickjs

BASE = "http://127.0.0.1:8080"
API_KEY = "tb3_notes_api_secret_2026"

_JS_HARNESS = r"""
var __calls = [];
var __elements = {};
var __created = [];
var __docListeners = {};

function __classHas(el, name) {
    if (!el || el.className === undefined || el.className === null) return false;
    return (' ' + String(el.className) + ' ').indexOf(' ' + name + ' ') >= 0;
}

function __makeElement(id) {
    return {
        id: id,
        tagName: 'DIV',
        textContent: '',
        value: '',
        innerHTML: '',
        children: [],
        className: '',
        listeners: {},
        addEventListener: function(type, cb) { this.listeners[type] = cb; },
        setAttribute: function(k, v) { this['attr_' + k] = v; },
        getAttribute: function(k) { return this['attr_' + k] || null; },
        appendChild: function(child) {
            this.children.push(child);
            __created.push(child);
            return child;
        },
        querySelectorAll: function() { return []; },
        closest: function(sel) {
            if (!sel) return null;
            var s = String(sel);
            var re = /\.([a-zA-Z0-9_-]+)/g;
            var m;
            while ((m = re.exec(s)) !== null) {
                if (__classHas(this, m[1])) return this;
            }
            return null;
        }
    };
}

function __stripParsedButtons() {
    __created = __created.filter(function(e) { return !e._fromParser; });
}

function __parseButtonsFromHtml(html) {
    if (!html) return;
    var re = /<button\b[^>]*>/gi;
    var bm;
    while ((bm = re.exec(html)) !== null) {
        var tag = bm[0];
        var clsM = /class\s*=\s*["']([^"']*)["']/.exec(tag);
        var cls = clsM ? clsM[1] : '';
        var btn = __makeElement('_btn' + __created.length);
        btn.tagName = 'BUTTON';
        btn.className = cls;
        btn.listeners = {};
        var dm = /onclick\s*=\s*"([^"]*)"/.exec(tag);
        var sm = /onclick\s*=\s*'([^']*)'/.exec(tag);
        var code = dm ? dm[1] : (sm ? sm[1] : '');
        if (code) {
            btn.listeners.click = (function(c) {
                return function() {
                    try { eval(c); } catch (e) {}
                };
            })(code);
        }
        btn._fromParser = true;
        __created.push(btn);
    }
}

function __makeNotesListElement() {
    var el = __makeElement('notes-list');
    Object.defineProperty(el, 'innerHTML', {
        set: function(v) {
            __stripParsedButtons();
            el._innerHTML = v || '';
            el.children = [];
            var html = el._innerHTML;
            var cardCount = (html.match(/note-card/g) || []).length;
            if (cardCount === 0 && html.indexOf('Note One') >= 0 && html.indexOf('Note Two') >= 0) {
                cardCount = 2;
            }
            if (cardCount === 0) {
                var eb = (html.match(/edit-btn/g) || []).length;
                if (eb >= 2) { cardCount = eb; }
            }
            var i;
            for (i = 0; i < cardCount; i++) {
                var c = __makeElement('_card' + i);
                c.className = 'note-card';
                el.children.push(c);
            }
            __parseButtonsFromHtml(html);
        },
        get: function() { return el._innerHTML || ''; }
    });
    return el;
}

globalThis.localStorage = {
    _data: {},
    getItem: function(k) { return this._data[k] === undefined ? null : this._data[k]; },
    setItem: function(k, v) { this._data[k] = String(v); },
    removeItem: function(k) { delete this._data[k]; }
};

globalThis.document = {
    getElementById: function(id) {
        if (!__elements[id]) {
            if (id === 'notes-list') { __elements[id] = __makeNotesListElement(); }
            else { __elements[id] = __makeElement(id); }
        }
        return __elements[id];
    },
    createElement: function(tag) {
        var nel = __makeElement('_d' + Math.random().toString(36).slice(2));
        nel.tagName = tag.toUpperCase();
        return nel;
    },
    addEventListener: function(type, cb) {
        __docListeners[type] = cb;
    },
    removeEventListener: function() {}
};

globalThis.window = {
    location: { protocol: 'http:', host: '127.0.0.1:8080' }
};

globalThis.__countClass = function(name) {
    return __created.filter(function(e) { return __classHas(e, name); }).length;
};

function __synthClickEvent(target, currentTarget) {
    return {
        target: target,
        currentTarget: currentTarget || null,
        preventDefault: function() {},
        stopPropagation: function() {}
    };
}

function __tryDelegatedClick(b) {
    var ids = ['notes-list', 'app', 'root', 'main', 'container'];
    var i, el, ev;
    for (i = 0; i < ids.length; i++) {
        el = document.getElementById(ids[i]);
        if (el && el.listeners && el.listeners.click) {
            ev = __synthClickEvent(b, el);
            el.listeners.click(ev);
            return true;
        }
    }
    if (__docListeners.click) {
        ev = __synthClickEvent(b, globalThis.document);
        __docListeners.click(ev);
        return true;
    }
    return false;
}

globalThis.__clickDeleteFirst = function() {
    var dbs = __created.filter(function(e) { return __classHas(e, 'delete-btn'); });
    if (dbs.length === 0) return false;
    var b = dbs[0];
    if (b.listeners.click) {
        b.listeners.click(__synthClickEvent(b, b));
        return true;
    }
    return __tryDelegatedClick(b);
};

globalThis.__clickEditFirst = function() {
    var ebs = __created.filter(function(e) { return __classHas(e, 'edit-btn'); });
    if (ebs.length === 0) return false;
    var b = ebs[0];
    if (b.listeners.click) {
        b.listeners.click(__synthClickEvent(b, b));
        return true;
    }
    return __tryDelegatedClick(b);
};

globalThis.fetch = async function(url, opts) {
    opts = opts || {};
    var method = opts.method || 'GET';
    var headers = opts.headers || {};
    __calls.push({ url: url, method: method, body: opts.body || null, headers: headers });

    if (url === '/api/notes' && method === 'GET') {
        return { ok: true, json: async function() {
            return [
                { id: 1, title: 'Note One', content: 'Body One' },
                { id: 2, title: 'Note Two', content: 'Body Two' }
            ];
        }};
    }
    if (url === '/api/notes' && method === 'POST') {
        var parsed = JSON.parse(opts.body);
        return { ok: true, json: async function() {
            return { id: 3, title: parsed.title, content: parsed.content };
        }};
    }
    if (method === 'PUT') {
        var p2 = JSON.parse(opts.body);
        return { ok: true, json: async function() {
            return { id: 1, title: p2.title, content: p2.content };
        }};
    }
    if (method === 'DELETE') {
        return { ok: true, json: async function() {
            return { status: 'deleted' };
        }};
    }
    return { ok: true, json: async function() { return {}; } };
};

globalThis.__snapshot = function() {
    return JSON.stringify({
        calls: __calls,
        titleVal: document.getElementById('note-title').value,
        contentVal: document.getElementById('note-content').value,
        listChildren: document.getElementById('notes-list').children.length,
        createdCount: __created.length
    });
};
"""


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


def _create_note_api(title: str, content: str) -> int:
    code, payload = _json_request(
        "POST", "/api/notes", {"title": title, "content": content}
    )
    assert code == 201
    return int(payload["id"])


def _get_js() -> str:
    with urllib.request.urlopen(f"{BASE}/app.js", timeout=5) as resp:
        return resp.read().decode("utf-8")


def _run_harness() -> dict:
    ctx = quickjs.Context()
    ctx.eval(_JS_HARNESS)
    ctx.eval(_get_js())
    while ctx.execute_pending_job():
        pass
    return json.loads(ctx.eval("__snapshot()"))


def _expected_api_key_from_file() -> str:
    path = Path("/app/config/api.key")
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return API_KEY


def _header_value_case_insensitive(headers: dict, name: str) -> str | None:
    for key, value in (headers or {}).items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


def _assert_list_refresh_after_call(
    calls: list,
    method: str,
    url_predicate: Callable[[str], bool],
) -> None:
    """There must be a GET /api/notes (list) after the last matching mutation."""
    last_idx: int | None = None
    for i, c in enumerate(calls):
        if c.get("method") != method:
            continue
        url = c.get("url") or ""
        if not url_predicate(url):
            continue
        last_idx = i
    assert last_idx is not None, f"Expected at least one {method} matching predicate"
    tail = calls[last_idx + 1 :]
    refreshed = any(
        c.get("method") == "GET" and c.get("url") == "/api/notes" for c in tail
    )
    assert refreshed, (
        f"Expected GET /api/notes to refresh the list after {method}; "
        f"calls after index {last_idx}: {tail!r}"
    )


class TestMilestone3:
    def test_js_fetches_notes_on_load(self):
        """app.js must call GET /api/notes when the script is loaded."""
        snap = _run_harness()
        get_calls = [
            c for c in snap["calls"] if c["url"] == "/api/notes" and c["method"] == "GET"
        ]
        assert len(get_calls) >= 1
    
    
    def test_js_renders_note_cards(self):
        """The mock GET response with two notes must produce child elements in notes-list."""
        snap = _run_harness()
        assert snap["listChildren"] >= 2
    
    
    def test_js_renders_edit_and_delete_buttons(self):
        """Each rendered note must include edit-btn and delete-btn elements."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        edit_count = int(
            ctx.eval(
                "__countClass('edit-btn')"
            )
        )
        del_count = int(
            ctx.eval(
                "__countClass('delete-btn')"
            )
        )
        assert edit_count >= 2
        assert del_count >= 2
    
    
    def test_js_form_submit_posts_to_api(self):
        """Submitting the form without an active edit must POST to /api/notes."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        ctx.eval("document.getElementById('note-title').value = 'New'")
        ctx.eval("document.getElementById('note-content').value = 'Content'")
        ctx.eval(
            "var f = document.getElementById('note-form');"
            "if (f.listeners.submit) f.listeners.submit({preventDefault:function(){}})"
        )
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        post_calls = [
            c for c in calls if c["method"] == "POST" and c["url"] == "/api/notes"
        ]
        assert len(post_calls) >= 1
        body = json.loads(post_calls[0]["body"])
        assert body.get("title") == "New"
        assert body.get("content") == "Content"

    def test_js_form_clears_after_create(self):
        """After a successful create, form fields must be emptied."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        ctx.eval("document.getElementById('note-title').value = 'Temp'")
        ctx.eval("document.getElementById('note-content').value = 'Body'")
        ctx.eval(
            "var f = document.getElementById('note-form');"
            "if (f.listeners.submit) f.listeners.submit({preventDefault:function(){}})"
        )
        while ctx.execute_pending_job():
            pass
        title_val = ctx.eval("document.getElementById('note-title').value")
        content_val = ctx.eval("document.getElementById('note-content').value")
        assert title_val == ""
        assert content_val == ""

    def test_js_refreshes_list_after_create(self):
        """After a successful POST create, the notes list must be fetched again."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        ctx.eval("document.getElementById('note-title').value = 'New'")
        ctx.eval("document.getElementById('note-content').value = 'Content'")
        ctx.eval(
            "var f = document.getElementById('note-form');"
            "if (f.listeners.submit) f.listeners.submit({preventDefault:function(){}})"
        )
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        _assert_list_refresh_after_call(calls, "POST", lambda u: u == "/api/notes")
    
    
    def test_js_refreshes_list_after_update(self):
        """After a successful PUT update, the notes list must be fetched again."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        assert int(ctx.eval("__countClass('edit-btn')")) >= 1, "No edit buttons found"
        assert ctx.eval("__clickEditFirst()")
        while ctx.execute_pending_job():
            pass
        ctx.eval("document.getElementById('note-title').value = 'Updated'")
        ctx.eval("document.getElementById('note-content').value = 'Revised body'")
        ctx.eval(
            "var f = document.getElementById('note-form');"
            "if (f.listeners.submit) f.listeners.submit({preventDefault:function(){}})"
        )
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        put_calls = [
            c
            for c in calls
            if c["method"] == "PUT" and str(c["url"]).startswith("/api/notes/")
        ]
        assert len(put_calls) >= 1
        put_body = json.loads(put_calls[-1]["body"])
        assert put_body.get("title") == "Updated"
        assert put_body.get("content") == "Revised body"
        _assert_list_refresh_after_call(
            calls, "PUT", lambda u: str(u).startswith("/api/notes/")
        )
    
    
    def test_js_refreshes_list_after_delete(self):
        """After a successful DELETE, the notes list must be fetched again."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        assert ctx.eval("__clickDeleteFirst()")
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        _assert_list_refresh_after_call(
            calls, "DELETE", lambda u: str(u).startswith("/api/notes/")
        )
    
    
    def test_js_delete_calls_delete_api(self):
        """Clicking a delete button must call DELETE on the API."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        assert ctx.eval("__clickDeleteFirst()")
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        del_calls = [c for c in calls if c["method"] == "DELETE"]
        assert len(del_calls) >= 1
    
    
    def test_js_get_requests_omit_api_key_header(self):
        """GET requests from JS must not include X-API-Key (list load and any refresh)."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        get_calls = [c for c in calls if c.get("method") == "GET"]
        assert len(get_calls) >= 1, "Expected at least one GET (e.g. initial list fetch)"
        for c in get_calls:
            headers = c.get("headers") or {}
            lower_keys = {str(k).lower() for k in headers}
            assert "x-api-key" not in lower_keys, (
                "GET must not send X-API-Key; got headers: "
                + json.dumps(headers)
            )
    
    
    def test_js_post_includes_api_key_header(self):
        """POST requests from JS must include X-API-Key header."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        ctx.eval("document.getElementById('note-title').value = 'Auth Test'")
        ctx.eval("document.getElementById('note-content').value = 'Body'")
        ctx.eval(
            "var f = document.getElementById('note-form');"
            "if (f.listeners.submit) f.listeners.submit({preventDefault:function(){}})"
        )
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        post_calls = [
            c for c in calls if c["method"] == "POST" and c["url"] == "/api/notes"
        ]
        assert len(post_calls) >= 1
        headers = post_calls[0].get("headers", {})
        api_key = _header_value_case_insensitive(headers, "X-API-Key")
        assert api_key is not None, "POST must include X-API-Key header"
        assert api_key == _expected_api_key_from_file()
    
    
    def test_js_post_includes_json_content_type_header(self):
        """POST requests from JS must include Content-Type: application/json."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        ctx.eval("document.getElementById('note-title').value = 'CT Test'")
        ctx.eval("document.getElementById('note-content').value = 'Body'")
        ctx.eval(
            "var f = document.getElementById('note-form');"
            "if (f.listeners.submit) f.listeners.submit({preventDefault:function(){}})"
        )
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        post_calls = [
            c for c in calls if c["method"] == "POST" and c["url"] == "/api/notes"
        ]
        assert len(post_calls) >= 1
        headers = post_calls[0].get("headers", {})
        content_type = _header_value_case_insensitive(headers, "Content-Type")
        assert content_type == "application/json"
    
    
    def test_js_delete_includes_api_key_header(self):
        """DELETE requests from JS must include X-API-Key header."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        assert ctx.eval("__clickDeleteFirst()")
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        del_calls = [c for c in calls if c["method"] == "DELETE"]
        assert len(del_calls) >= 1
        headers = del_calls[0].get("headers", {})
        api_key = _header_value_case_insensitive(headers, "X-API-Key")
        assert api_key is not None, "DELETE must include X-API-Key header"
        assert api_key == _expected_api_key_from_file()
    
    
    def test_js_delete_includes_json_content_type_header(self):
        """DELETE requests from JS must include Content-Type: application/json."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        assert ctx.eval("__clickDeleteFirst()")
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        del_calls = [c for c in calls if c["method"] == "DELETE"]
        assert len(del_calls) >= 1
        headers = del_calls[0].get("headers", {})
        content_type = _header_value_case_insensitive(headers, "Content-Type")
        assert content_type == "application/json"
    
    
    def test_js_put_includes_api_key_header(self):
        """PUT requests from JS must include X-API-Key header."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        if int(ctx.eval("__countClass('edit-btn')")) > 0:
            assert ctx.eval("__clickEditFirst()")
            while ctx.execute_pending_job():
                pass
            ctx.eval(
                "var f = document.getElementById('note-form');"
                "if (f.listeners.submit) f.listeners.submit({preventDefault:function(){}})"
            )
            while ctx.execute_pending_job():
                pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        put_calls = [c for c in calls if c["method"] == "PUT"]
        assert len(put_calls) >= 1, "Edit+submit must trigger a PUT request"
        headers = put_calls[0].get("headers", {})
        api_key = _header_value_case_insensitive(headers, "X-API-Key")
        assert api_key is not None, "PUT must include X-API-Key header"
        assert api_key == _expected_api_key_from_file()
    
    
    def test_js_put_includes_json_content_type_header(self):
        """PUT requests from JS must include Content-Type: application/json."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        if int(ctx.eval("__countClass('edit-btn')")) > 0:
            assert ctx.eval("__clickEditFirst()")
            while ctx.execute_pending_job():
                pass
            ctx.eval(
                "var f = document.getElementById('note-form');"
                "if (f.listeners.submit) f.listeners.submit({preventDefault:function(){}})"
            )
            while ctx.execute_pending_job():
                pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        put_calls = [c for c in calls if c["method"] == "PUT"]
        assert len(put_calls) >= 1, "Edit+submit must trigger a PUT request"
        headers = put_calls[0].get("headers", {})
        content_type = _header_value_case_insensitive(headers, "Content-Type")
        assert content_type == "application/json"
    
    
    def test_js_edit_button_loads_note_into_form(self):
        """Clicking the edit button must populate the form fields with the note data."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        assert int(ctx.eval("__countClass('edit-btn')")) >= 1, "No edit buttons found"
        assert ctx.eval("__clickEditFirst()")
        while ctx.execute_pending_job():
            pass
        title_val = ctx.eval("document.getElementById('note-title').value")
        content_val = ctx.eval("document.getElementById('note-content').value")
        assert title_val == "Note One", "Edit must load the correct note title"
        assert content_val == "Body One", "Edit must load the correct note content"

    def test_js_form_clears_after_update(self):
        """After a successful update (edit+submit), form fields must be cleared."""
        ctx = quickjs.Context()
        ctx.eval(_JS_HARNESS)
        ctx.eval(_get_js())
        while ctx.execute_pending_job():
            pass
        assert int(ctx.eval("__countClass('edit-btn')")) >= 1, "No edit buttons found"
        assert ctx.eval("__clickEditFirst()")
        while ctx.execute_pending_job():
            pass
        ctx.eval(
            "var f = document.getElementById('note-form');"
            "if (f.listeners.submit) f.listeners.submit({preventDefault:function(){}})"
        )
        while ctx.execute_pending_job():
            pass
        title_val = ctx.eval("document.getElementById('note-title').value")
        content_val = ctx.eval("document.getElementById('note-content').value")
        assert title_val == "", "Form title must be cleared after update"
        assert content_val == "", "Form content must be cleared after update"
        ctx.eval("document.getElementById('note-title').value = 'After'")
        ctx.eval("document.getElementById('note-content').value = 'New note'")
        ctx.eval(
            "var f = document.getElementById('note-form');"
            "if (f.listeners.submit) f.listeners.submit({preventDefault:function(){}})"
        )
        while ctx.execute_pending_job():
            pass
        calls = json.loads(ctx.eval("JSON.stringify(__calls)"))
        mutation_calls = [
            c for c in calls if c["method"] in ("POST", "PUT")
        ]
        assert len(mutation_calls) >= 1
        last_submit = mutation_calls[-1]
        assert last_submit["method"] == "POST", (
            "After update, the UI must leave revision mode and POST a new note"
        )
        assert last_submit["url"] == "/api/notes"
        follow_body = json.loads(last_submit["body"])
        assert follow_body.get("title") == "After"
        assert follow_body.get("content") == "New note"

    # --- End-to-end integration tests ---
    
    
    def test_e2e_create_and_retrieve_note(self):
        """Create a note via API and verify it is retrievable by id."""
        note_id = _create_note_api("E2E Create", "Integration body")
        code, note = _json_request("GET", f"/api/notes/{note_id}")
        assert code == 200
        assert note["title"] == "E2E Create"
    
    
    def test_e2e_update_and_verify_persistence(self):
        """Update a note and verify the change persists on re-fetch."""
        note_id = _create_note_api("Original Title", "Before edit")
        _json_request(
            "PUT",
            f"/api/notes/{note_id}",
            {"title": "Updated Title", "content": "Edited body"},
        )
        _, fetched = _json_request("GET", f"/api/notes/{note_id}")
        assert fetched["title"] == "Updated Title"
        assert fetched["content"] == "Edited body"
    
    
    def test_e2e_delete_and_verify_gone(self):
        """Delete a note and verify it is no longer accessible."""
        note_id = _create_note_api("Ephemeral", "Soon gone")
        code, _ = _json_request("DELETE", f"/api/notes/{note_id}")
        assert code == 200
        get_code, _ = _json_request("GET", f"/api/notes/{note_id}")
        assert get_code == 404
    
    
    def test_e2e_full_crud_cycle(self):
        """Create multiple notes, update one, delete another, verify final state."""
        id1 = _create_note_api("Note A", "Body A")
        id2 = _create_note_api("Note B", "Body B")
        id3 = _create_note_api("Note C", "Body C")
    
        _json_request(
            "PUT",
            f"/api/notes/{id2}",
            {"title": "Note B Updated", "content": "New B"},
        )
        _json_request("DELETE", f"/api/notes/{id1}")
    
        code1, _ = _json_request("GET", f"/api/notes/{id1}")
        assert code1 == 404, "Deleted note must return 404"
        code2, b_note = _json_request("GET", f"/api/notes/{id2}")
        assert code2 == 200
        assert b_note["title"] == "Note B Updated"
        code3, _ = _json_request("GET", f"/api/notes/{id3}")
        assert code3 == 200

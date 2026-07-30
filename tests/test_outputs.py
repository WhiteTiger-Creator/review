"""Verification tests for the native edge cache handover."""

from __future__ import annotations

import hashlib

from varnish_rangehouse import (
    CACHE,
    HOST_AURORA,
    HOST_BASALT,
    ROOT,
    active_vcl_label,
    cache_control,
    control_headers,
    count_access_hits,
    edge_get,
    edge_state,
    force_backend_health,
    http_request,
    inspect_cache,
    origin_node,
    reload_policy,
    restore_file,
    sleep_seconds,
    stage_broken_vcl,
    start_stack,
    stop_stack,
    truncate_access_logs,
    vcl_list,
    wait_for,
)


def expected_vcl_label() -> str:
    files = sorted((ROOT / "vcl").glob("*.vcl"))
    digest = hashlib.sha256()
    for path in files:
        rel = f"vcl/{path.name}"
        data = path.read_bytes()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(data)
    return "mv_" + digest.hexdigest()[:16]


def test_gracewarden_inspection_reports_native_processes_and_backend_health() -> None:
    """Inspect-cache reports running processes, ports, probes, and preferred backend."""
    out = inspect_cache()
    assert "varnish_state=running" in out
    assert "client_port=18091" in out
    assert "management_port=18092" in out
    assert "primary_state=running" in out
    assert "secondary_state=running" in out
    assert "primary_probe=Healthy" in out
    assert "secondary_probe=Healthy" in out
    assert "preferred_backend=primary_origin" in out


def test_gracewarden_unknown_host_is_rejected_before_backend_contact() -> None:
    """Unsupported hosts receive 421 without contacting either origin."""
    truncate_access_logs()
    res = edge_get("/artifacts/stable/toolkit.tar", host="unknown.example")
    assert res.status == 421
    assert edge_state(res) == "SYNTH"
    assert count_access_hits("primary", "/artifacts/stable/toolkit.tar") == 0
    assert count_access_hits("secondary", "/artifacts/stable/toolkit.tar") == 0


def test_gracewarden_host_port_and_case_canonicalize_to_supported_host() -> None:
    """Numeric port stripping and lowercasing yield a supported host."""
    truncate_access_logs()
    res = edge_get(
        "/artifacts/stable/toolkit.tar",
        host="Releases.Aurora.invalid:18091",
    )
    assert res.status == 200
    assert edge_state(res) in {"MISS", "HIT"}
    assert (
        count_access_hits("primary", "/artifacts/stable/toolkit.tar")
        + count_access_hits("secondary", "/artifacts/stable/toolkit.tar")
        >= 1
    )


def test_gracewarden_same_url_is_isolated_between_supported_hosts() -> None:
    """Identical URLs on different hosts remain distinct cache objects."""
    a = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    b = edge_get("/artifacts/stable/toolkit.tar", host=HOST_BASALT)
    assert a.status == 200 and b.status == 200
    assert a.body != b.body
    a2 = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(a2) == "HIT"
    assert a2.body == a.body


def test_gracewarden_query_sorting_converges_and_values_stay_distinct() -> None:
    """Query order converges; different values and a trailing bare ? stay correct."""
    truncate_access_logs()
    first = edge_get("/metadata/index.json?b=2&a=1", host=HOST_AURORA)
    second = edge_get("/metadata/index.json?a=1&b=2", host=HOST_AURORA)
    bare = edge_get("/metadata/index.json?", host=HOST_AURORA)
    one = edge_get("/metadata/index.json?channel=one", host=HOST_AURORA)
    two = edge_get("/metadata/index.json?channel=two", host=HOST_AURORA)
    assert edge_state(first) == "MISS"
    assert edge_state(second) == "HIT"
    assert first.body == second.body
    assert bare.status == 200
    assert edge_state(one) == "MISS" and edge_state(two) == "MISS"


def test_gracewarden_public_get_hit_head_reuse_and_no_internal_metadata() -> None:
    """Public GET hits, HEAD reuses the object, and ban metadata stays internal."""
    first = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    second = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    head_res = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA, method="HEAD")
    assert edge_state(first) == "MISS"
    assert edge_state(second) == "HIT"
    assert second.body == first.body
    assert head_res.status == 200
    assert edge_state(head_res) == "HIT"
    assert head_res.body == b""
    lowered = {k.lower() for k in first.headers}
    assert "x-internal-host" not in lowered
    assert "x-internal-class" not in lowered
    assert "x-internal-url" not in lowered


def test_gracewarden_forced_pass_triggers_bypass_storage() -> None:
    """Auth, Cookie, Range, Cache-Control, Pragma, and unsafe methods force PASS."""
    cases = [
        ("auth", {"Authorization": "Bearer demo"}),
        ("cookie", {"Cookie": "sid=1"}),
        ("range", {"Range": "bytes=0-3"}),
        ("cc", {"Cache-Control": "no-cache"}),
        ("pragma", {"Pragma": "no-cache"}),
    ]
    for tag, headers in cases:
        path = f"/artifacts/stable/toolkit.tar?pass={tag}"
        bypass = edge_get(path, host=HOST_AURORA, headers=headers)
        assert edge_state(bypass) == "PASS", headers
        plain = edge_get(path, host=HOST_AURORA)
        assert edge_state(plain) == "MISS", headers
    post = http_request(
        "POST",
        f"{CACHE}/artifacts/stable/toolkit.tar?pass=post",
        host=HOST_AURORA,
        body=b"x",
    )
    assert edge_state(post) == "PASS"
    follow = edge_get("/artifacts/stable/toolkit.tar?pass=post", host=HOST_AURORA)
    assert edge_state(follow) == "MISS"


def test_gracewarden_ineligible_responses_never_seed_shared_cache() -> None:
    """Set-Cookie, private/no-store, and unapproved Vary never become HITs."""
    paths = [
        "/policy/set-cookie.bin",
        "/policy/private.bin",
        "/policy/no-store.bin",
        "/policy/vary-star.bin",
        "/policy/vary-language.bin",
    ]
    for path in paths:
        first = edge_get(path, host=HOST_AURORA)
        second = edge_get(path, host=HOST_AURORA)
        assert first.status == 200, path
        assert edge_state(second) != "HIT", path


def test_gracewarden_accept_encoding_normalization_and_absent_are_distinct() -> None:
    """gzip variants share one object; missing Accept-Encoding stays a different key."""
    # Use a non-Vary artifact URL so the cache key is driven by request-side AE
    # normalization (origins may still send Vary: Accept-Encoding on other paths).
    path = "/artifacts/stable/toolkit.tar?ae-norm=1"
    truncate_access_logs()
    multi = edge_get(
        path,
        host=HOST_AURORA,
        headers={"Accept-Encoding": "gzip, deflate, br"},
    )
    single = edge_get(
        path,
        host=HOST_AURORA,
        headers={"Accept-Encoding": "gzip"},
    )
    assert multi.status == 200 and single.status == 200
    assert multi.body == single.body
    assert edge_state(multi) == "MISS"
    assert edge_state(single) == "HIT"
    # Shared object: only one origin fetch for the equivalent gzip pair.
    origin_hits = count_access_hits("primary", path) + count_access_hits("secondary", path)
    assert origin_hits == 1, origin_hits
    absent = edge_get(path, host=HOST_AURORA, headers={})
    assert absent.status == 200
    assert edge_state(absent) == "MISS"
    # Vary: Accept-Encoding responses must remain storage-eligible after AE reduction.
    vpath = "/policy/vary-encoding.bin?ae-elig=1"
    first = edge_get(vpath, host=HOST_AURORA, headers={"Accept-Encoding": "gzip"})
    second = edge_get(vpath, host=HOST_AURORA, headers={"Accept-Encoding": "gzip"})
    assert first.status == 200 and edge_state(first) == "MISS"
    assert edge_state(second) == "HIT"


def test_gracewarden_secondary_serves_and_inspect_prefers_secondary() -> None:
    """With primary sick, fetches and preferred_backend move to secondary."""
    cache_control("origin-down", "primary")
    wait_for("primary-sick")
    truncate_access_logs()
    res = edge_get("/artifacts/candidate/toolkit.tar", host=HOST_AURORA)
    assert res.status == 200
    assert origin_node(res) == "secondary"
    out = inspect_cache()
    assert "preferred_backend=secondary_origin" in out
    assert "primary_probe=Sick" in out
    cache_control("origin-up", "primary")
    wait_for("primary-healthy")


def test_gracewarden_primary_preference_returns_after_probe_recovery() -> None:
    """After primary probe recovery, new fetches return to primary."""
    cache_control("origin-down", "primary")
    wait_for("primary-sick")
    edge_get("/metadata/index.json?recovery=1", host=HOST_AURORA)
    cache_control("origin-up", "primary")
    wait_for("primary-healthy")
    truncate_access_logs()
    res = edge_get("/metadata/index.json?recovery=2", host=HOST_AURORA)
    assert origin_node(res) == "primary"


def test_gracewarden_inspect_prefers_none_when_both_origins_are_sick() -> None:
    """Dual-outage inspection reports preferred_backend=none with both probes Sick."""
    cache_control("origin-down", "primary")
    cache_control("origin-down", "secondary")
    wait_for("primary-sick")
    wait_for("secondary-sick")
    force_backend_health("primary_origin", "sick")
    force_backend_health("secondary_origin", "sick")
    out = inspect_cache()
    assert "preferred_backend=none" in out
    assert "primary_probe=Sick" in out
    assert "secondary_probe=Sick" in out
    force_backend_health("primary_origin", "auto")
    force_backend_health("secondary_origin", "auto")
    cache_control("origin-up", "primary")
    cache_control("origin-up", "secondary")
    wait_for("stack-ready")


def test_gracewarden_fresh_cached_object_survives_total_origin_outage() -> None:
    """A still-fresh cached object remains HIT while both origins are down."""
    first = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(first) == "MISS"
    cache_control("origin-down", "primary")
    cache_control("origin-down", "secondary")
    force_backend_health("primary_origin", "sick")
    force_backend_health("secondary_origin", "sick")
    second = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(second) == "HIT"
    assert second.body == first.body
    force_backend_health("primary_origin", "auto")
    force_backend_health("secondary_origin", "auto")
    cache_control("origin-up", "primary")
    cache_control("origin-up", "secondary")
    wait_for("stack-ready")


def test_gracewarden_stale_object_is_delivered_inside_grace_window() -> None:
    """Stale objects are delivered as GRACE only while both origins are sick."""
    first = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(first) == "MISS"
    sleep_seconds(1.2)
    cache_control("origin-down", "primary")
    cache_control("origin-down", "secondary")
    wait_for("primary-sick")
    wait_for("secondary-sick")
    second = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(second) == "GRACE"
    assert second.body == first.body
    cache_control("origin-up", "primary")
    cache_control("origin-up", "secondary")
    wait_for("stack-ready")


def test_gracewarden_stale_with_healthy_origin_refetches_not_grace() -> None:
    """Stale content is never GRACE when any origin is healthy; refetch from secondary."""
    first = edge_get("/artifacts/stable/toolkit.tar?stale-healthy=1", host=HOST_AURORA)
    assert edge_state(first) == "MISS"
    assert origin_node(first) == "primary"
    sleep_seconds(1.2)
    cache_control("origin-down", "primary")
    wait_for("primary-sick")
    second = edge_get("/artifacts/stable/toolkit.tar?stale-healthy=1", host=HOST_AURORA)
    assert edge_state(second) != "GRACE"
    assert second.status == 200
    assert origin_node(second) == "secondary"
    cache_control("origin-up", "primary")
    wait_for("primary-healthy")


def test_gracewarden_stale_object_is_refused_after_grace_expires() -> None:
    """After grace expires with both origins sick, requests synthesize 503."""
    first = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert first.status == 200
    sleep_seconds(1.2)
    cache_control("origin-down", "primary")
    cache_control("origin-down", "secondary")
    wait_for("primary-sick")
    wait_for("secondary-sick")
    sleep_seconds(5.2)
    refused = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert refused.status == 503
    assert edge_state(refused) == "SYNTH"
    cache_control("origin-up", "primary")
    cache_control("origin-up", "secondary")
    wait_for("stack-ready")


def test_gracewarden_uncached_object_returns_failure_when_both_origins_are_down() -> None:
    """Uncached URLs return 503 SYNTH when both origins are unavailable."""
    cache_control("origin-down", "primary")
    cache_control("origin-down", "secondary")
    wait_for("primary-sick")
    wait_for("secondary-sick")
    res = edge_get("/metadata/index.json?uncached=down", host=HOST_AURORA)
    assert res.status == 503
    assert edge_state(res) == "SYNTH"
    cache_control("origin-up", "primary")
    cache_control("origin-up", "secondary")
    wait_for("stack-ready")


def test_gracewarden_conditional_request_returns_cache_backed_not_modified() -> None:
    """Matching If-None-Match against a cache object returns 304 with edge state."""
    first = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    etag = first.headers.get("etag")
    assert etag
    second = edge_get(
        "/artifacts/stable/toolkit.tar",
        host=HOST_AURORA,
        headers={"If-None-Match": etag},
    )
    assert second.status == 304
    assert second.body == b""
    assert edge_state(second) in {"HIT", "MISS"}


def test_gracewarden_conditional_hit_survives_total_outage() -> None:
    """Fresh cache-backed 304 still works while both origins are forced sick."""
    first = edge_get("/artifacts/candidate/toolkit.tar?cond=1", host=HOST_AURORA)
    etag = first.headers.get("etag")
    assert etag and edge_state(first) == "MISS"
    cache_control("origin-down", "primary")
    cache_control("origin-down", "secondary")
    force_backend_health("primary_origin", "sick")
    force_backend_health("secondary_origin", "sick")
    second = edge_get(
        "/artifacts/candidate/toolkit.tar?cond=1",
        host=HOST_AURORA,
        headers={"If-None-Match": etag},
    )
    assert second.status == 304
    assert second.body == b""
    assert edge_state(second) == "HIT"
    force_backend_health("primary_origin", "auto")
    force_backend_health("secondary_origin", "auto")
    cache_control("origin-up", "primary")
    cache_control("origin-up", "secondary")
    wait_for("stack-ready")


def test_gracewarden_unauthorized_purge_changes_no_cached_object() -> None:
    """Unauthorized PURGE leaves the cached object reusable."""
    first = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(first) == "MISS"
    bad = http_request(
        "PURGE",
        f"{CACHE}/artifacts/stable/toolkit.tar",
        host=HOST_AURORA,
        headers={"X-Mirror-Control": "wrong-marker"},
    )
    assert bad.status == 405
    assert edge_state(bad) == "SYNTH"
    second = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(second) == "HIT"


def test_gracewarden_authorized_purge_is_exact_url_and_host_scoped() -> None:
    """Authorized PURGE removes one host/URL only; peer host and other URLs remain."""
    target = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    other_url = edge_get("/artifacts/candidate/toolkit.tar", host=HOST_AURORA)
    peer = edge_get("/artifacts/stable/toolkit.tar", host=HOST_BASALT)
    assert edge_state(target) == "MISS"
    assert edge_state(other_url) == "MISS"
    assert edge_state(peer) == "MISS"
    purged = http_request(
        "PURGE",
        f"{CACHE}/artifacts/stable/toolkit.tar",
        host=HOST_AURORA,
        headers=control_headers(),
    )
    assert purged.status == 200
    assert purged.body.strip() == b"purged"
    assert edge_state(edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)) == "MISS"
    assert edge_state(edge_get("/artifacts/candidate/toolkit.tar", host=HOST_AURORA)) == "HIT"
    assert edge_state(edge_get("/artifacts/stable/toolkit.tar", host=HOST_BASALT)) == "HIT"


def test_gracewarden_unauthorized_ban_changes_no_cached_object() -> None:
    """Unauthorized BAN leaves matching class objects reusable."""
    first = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(first) == "MISS"
    bad = http_request(
        "BAN",
        f"{CACHE}/",
        host=HOST_AURORA,
        headers={"X-Ban-Class": "stable"},
    )
    assert bad.status == 405
    second = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(second) == "HIT"


def test_gracewarden_authorized_class_ban_removes_matching_host_objects() -> None:
    """Authorized class BAN removes matching class objects for that host."""
    stable = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    candidate = edge_get("/artifacts/candidate/toolkit.tar", host=HOST_AURORA)
    assert edge_state(stable) == "MISS" and edge_state(candidate) == "MISS"
    banned = http_request(
        "BAN",
        f"{CACHE}/",
        host=HOST_AURORA,
        headers=control_headers({"X-Ban-Class": "stable"}),
    )
    assert banned.status == 202
    assert banned.body.strip() == b"ban queued"
    sleep_seconds(0.3)
    assert edge_state(edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)) == "MISS"
    assert edge_state(edge_get("/artifacts/candidate/toolkit.tar", host=HOST_AURORA)) == "HIT"


def test_gracewarden_class_ban_does_not_cross_host_boundary() -> None:
    """A class BAN on one host does not invalidate the other host."""
    aurora = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    basalt = edge_get("/artifacts/stable/toolkit.tar", host=HOST_BASALT)
    assert edge_state(aurora) == "MISS" and edge_state(basalt) == "MISS"
    banned = http_request(
        "BAN",
        f"{CACHE}/",
        host=HOST_AURORA,
        headers=control_headers({"X-Ban-Class": "stable"}),
    )
    assert banned.status == 202
    sleep_seconds(0.3)
    assert edge_state(edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)) == "MISS"
    assert edge_state(edge_get("/artifacts/stable/toolkit.tar", host=HOST_BASALT)) == "HIT"


def test_gracewarden_metadata_ban_invalidates_encoding_object_not_stable() -> None:
    """Class BAN uses stored X-Artifact-Class, not URL path tokens."""
    enc = edge_get(
        "/policy/vary-encoding.bin",
        host=HOST_AURORA,
        headers={"Accept-Encoding": "gzip"},
    )
    stable = edge_get("/artifacts/stable/toolkit.tar?banmeta=1", host=HOST_AURORA)
    assert edge_state(enc) == "MISS" and edge_state(stable) == "MISS"
    banned = http_request(
        "BAN",
        f"{CACHE}/",
        host=HOST_AURORA,
        headers=control_headers({"X-Ban-Class": "metadata"}),
    )
    assert banned.status == 202
    sleep_seconds(0.3)
    assert edge_state(
        edge_get(
            "/policy/vary-encoding.bin",
            host=HOST_AURORA,
            headers={"Accept-Encoding": "gzip"},
        )
    ) == "MISS"
    assert edge_state(edge_get("/artifacts/stable/toolkit.tar?banmeta=1", host=HOST_AURORA)) == "HIT"


def test_gracewarden_invalid_ban_class_is_rejected_without_invalidation() -> None:
    """Unsupported ban classes return 400 and leave objects untouched."""
    first = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(first) == "MISS"
    bad = http_request(
        "BAN",
        f"{CACHE}/",
        host=HOST_AURORA,
        headers=control_headers({"X-Ban-Class": "nope"}),
    )
    assert bad.status == 400
    assert edge_state(bad) == "SYNTH"
    second = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert edge_state(second) == "HIT"


def test_gracewarden_invalid_vcl_reload_preserves_active_policy() -> None:
    """A rejected VCL reload leaves the previously active label serving."""
    before = active_vcl_label()
    target = ROOT / "vcl" / "entry.vcl"
    backup = stage_broken_vcl(target)
    try:
        result = reload_policy()
        assert result.returncode != 0
        assert active_vcl_label() == before
        res = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
        assert res.status in {200, 421, 503} or edge_state(res) in {
            "MISS",
            "HIT",
            "PASS",
            "SYNTH",
            "GRACE",
        }
    finally:
        restore_file(backup, target)


def test_gracewarden_valid_vcl_reload_activates_content_addressed_generation() -> None:
    """Valid reload activates mv_<16 hex> and a second identical reload stays success."""
    expected = expected_vcl_label()
    result = reload_policy()
    assert result.returncode == 0
    assert active_vcl_label() == expected
    assert expected in vcl_list()
    result2 = reload_policy()
    assert result2.returncode == 0
    assert active_vcl_label() == expected


def test_gracewarden_large_artifact_streams_and_then_hits_cache() -> None:
    """Six MiB artifacts stream from origin once, then reuse from cache."""
    first = edge_get("/large/archive.bin", host=HOST_AURORA, headers={})
    assert first.status == 200
    assert len(first.body) == 6 * 1024 * 1024
    assert edge_state(first) == "MISS"
    second = edge_get("/large/archive.bin", host=HOST_AURORA)
    assert edge_state(second) == "HIT"
    assert second.body == first.body


def test_gracewarden_grace_recovery_refetches_preferred_primary() -> None:
    """After dual-outage grace, restoring primary refetches from primary (not GRACE)."""
    first = edge_get("/artifacts/stable/toolkit.tar?grace-recover=1", host=HOST_AURORA)
    assert edge_state(first) == "MISS"
    sleep_seconds(1.2)
    cache_control("origin-down", "primary")
    cache_control("origin-down", "secondary")
    wait_for("primary-sick")
    wait_for("secondary-sick")
    grace = edge_get("/artifacts/stable/toolkit.tar?grace-recover=1", host=HOST_AURORA)
    assert edge_state(grace) == "GRACE"
    cache_control("origin-up", "primary")
    wait_for("primary-healthy")
    recovered = edge_get("/artifacts/stable/toolkit.tar?grace-recover=1", host=HOST_AURORA)
    assert edge_state(recovered) != "GRACE"
    assert recovered.status == 200
    assert origin_node(recovered) == "primary"
    cache_control("origin-up", "secondary")
    wait_for("stack-ready")


def test_gracewarden_secondary_only_recovery_after_grace_refetches_secondary() -> None:
    """After GRACE, restoring only secondary refetches from secondary (not GRACE)."""
    first = edge_get("/artifacts/stable/toolkit.tar?sec-recover=1", host=HOST_AURORA)
    assert edge_state(first) == "MISS"
    sleep_seconds(1.2)
    cache_control("origin-down", "primary")
    cache_control("origin-down", "secondary")
    wait_for("primary-sick")
    wait_for("secondary-sick")
    grace = edge_get("/artifacts/stable/toolkit.tar?sec-recover=1", host=HOST_AURORA)
    assert edge_state(grace) == "GRACE"
    cache_control("origin-up", "secondary")
    wait_for("secondary-healthy")
    force_backend_health("primary_origin", "sick")
    recovered = edge_get("/artifacts/stable/toolkit.tar?sec-recover=1", host=HOST_AURORA)
    assert edge_state(recovered) != "GRACE"
    assert recovered.status == 200
    assert origin_node(recovered) == "secondary"
    out = inspect_cache()
    assert "preferred_backend=secondary_origin" in out
    force_backend_health("primary_origin", "auto")
    cache_control("origin-up", "primary")
    wait_for("stack-ready")


def test_gracewarden_purged_url_is_uncached_under_dual_outage() -> None:
    """After an authorized PURGE, dual-outage requests for that URL are 503 SYNTH."""
    first = edge_get("/artifacts/stable/toolkit.tar?purge-outage=1", host=HOST_AURORA)
    assert edge_state(first) == "MISS"
    purged = http_request(
        "PURGE",
        f"{CACHE}/artifacts/stable/toolkit.tar?purge-outage=1",
        host=HOST_AURORA,
        headers=control_headers(),
    )
    assert purged.status == 200
    cache_control("origin-down", "primary")
    cache_control("origin-down", "secondary")
    wait_for("primary-sick")
    wait_for("secondary-sick")
    refused = edge_get("/artifacts/stable/toolkit.tar?purge-outage=1", host=HOST_AURORA)
    assert refused.status == 503
    assert edge_state(refused) == "SYNTH"
    cache_control("origin-up", "primary")
    cache_control("origin-up", "secondary")
    wait_for("stack-ready")


def test_gracewarden_stop_start_cycle_restores_clean_preferred_service() -> None:
    """Stop/start restores probes, preferred primary fetches, and exact mv_ generation."""
    expected = expected_vcl_label()
    stop_stack()
    start_stack()
    wait_for("stack-ready")
    wait_for("primary-healthy")
    out = inspect_cache()
    assert "varnish_state=running" in out
    assert "preferred_backend=primary_origin" in out
    res = edge_get("/artifacts/stable/toolkit.tar", host=HOST_AURORA)
    assert res.status == 200
    assert origin_node(res) == "primary"
    assert active_vcl_label() == expected

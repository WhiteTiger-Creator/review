import copy
import hashlib
import json
import subprocess
from pathlib import Path


APP = Path("/app")
REQ = APP / "task_file" / "request.json"
REG = APP / "task_file" / "registry.json"
OUT = APP / "task_file" / "lock.json"
GO = Path("/usr/local/go/bin/go")


def req(name, min_v=None, min_i=True, max_v=None, max_i=False, features=None, allow_yanked=False):
    return {
        "name": name,
        "min": min_v,
        "min_inclusive": min_i,
        "max": max_v,
        "max_inclusive": max_i,
        "features": list(features or []),
        "allow_yanked": allow_yanked,
    }


def seal(name, version):
    return hashlib.sha256(f"{name}@{version}".encode()).hexdigest()


def provide(name, version):
    return {"name": name, "version": version}


def pkg(
    name,
    version,
    platforms=None,
    yanked=False,
    features=None,
    deps=None,
    provides=None,
    conflicts=None,
    bad=False,
):
    value = seal(name, version)
    if bad:
        value = "0" * 64
    return {
        "name": name,
        "version": version,
        "platforms": list(platforms or ["any"]),
        "hash": value,
        "yanked": yanked,
        "features": list(features or []),
        "deps": copy.deepcopy(list(deps or [])),
        "provides": copy.deepcopy(list(provides or [])),
        "conflicts": copy.deepcopy(list(conflicts or [])),
    }


PUBLIC_REQUEST = {
    "platform": "linux-x64",
    "roots": [
        req("atlas", "1.0.0", True, "3.0.0", False, ["seal"], False),
        req("beacon", "1.0.0", True, None, False, [], False),
    ],
}

PUBLIC_REGISTRY = {
    "packages": [
        pkg("atlas", "2.2.0", ["linux-x64"], False, ["seal"], [
            req("core", "2.0.0", True, "3.0.0", False, ["tls"], False),
            req("scribe", "1.0.0", True, "2.0.0", False, [], False),
        ]),
        pkg("atlas", "2.4.0", ["linux-x64"], False, ["seal"], [
            req("core", "2.2.0", True, "3.0.0", False, ["tls"], False),
            req("rune", "1.0.0", True, "2.0.0", False, [], False),
        ]),
        pkg("beacon", "1.3.0", ["any"], False, [], [
            req("core", "2.1.0", True, "2.4.0", False, [], False),
        ]),
        pkg("core", "2.1.0", ["linux-x64", "linux-arm64"], False, ["tls"], []),
        pkg("core", "2.3.0", ["linux-x64"], True, ["tls"], []),
        pkg("scribe", "1.7.0", ["any"], False, [], []),
        pkg("rune", "1.6.0", ["linux-x64"], False, [], [], bad=True),
    ],
}


def version_tuple(value):
    return tuple(int(part) for part in value.split("."))


def in_range(version, item):
    current = version_tuple(version)
    if item["min"] is not None:
        low = version_tuple(item["min"])
        if current < low or (current == low and not item["min_inclusive"]):
            return False
    if item["max"] is not None:
        high = version_tuple(item["max"])
        if current > high or (current == high and not item["max_inclusive"]):
            return False
    return True


def provided_pairs(candidate):
    pairs = [provide(candidate["name"], candidate["version"])]
    pairs.extend(candidate.get("provides", []))
    return pairs


def matching_pair(candidate, name):
    for item in provided_pairs(candidate):
        if item["name"] == name:
            return item
    return None


def matches_requirement(candidate, item):
    for pair in provided_pairs(candidate):
        if pair["name"] == item["name"] and in_range(pair["version"], item):
            return True
    return False


def usable_for_group(candidate, items, platform):
    if not items:
        return False
    if platform not in candidate["platforms"] and "any" not in candidate["platforms"]:
        return False
    if candidate["hash"] != seal(candidate["name"], candidate["version"]):
        return False
    if not all(matches_requirement(candidate, item) for item in items):
        return False
    wanted = set()
    for item in items:
        wanted.update(item["features"])
    if not wanted.issubset(set(candidate["features"])):
        return False
    if candidate["yanked"] and not all(item["allow_yanked"] for item in items):
            return False
    return True


def selected_covers(chosen, name, items, platform):
    for candidate in chosen.values():
        if matching_pair(candidate, name) is not None and usable_for_group(candidate, items, platform):
            return True
    return False


def conflicts_ok(chosen):
    rows = list(chosen.values())
    for left in rows:
        for right in rows:
            if left is right:
                continue
            for item in left.get("conflicts", []):
                if matches_requirement(right, item):
                    return False
    return True


def add_item(groups, item):
    groups.setdefault(item["name"], []).append(copy.deepcopy(item))


def expected_lock(request, registry):
    by_cover = {}
    for candidate in registry["packages"]:
        for pair in provided_pairs(candidate):
            by_cover.setdefault(pair["name"], []).append(candidate)
    groups = {}
    for item in request["roots"]:
        add_item(groups, item)
    locks = []

    def walk(current, chosen):
        for name, items in current.items():
            if name in chosen and not usable_for_group(chosen[name], items, request["platform"]):
                return
        if not conflicts_ok(chosen):
            return
        pending = sorted(
            name for name, items in current.items()
            if not selected_covers(chosen, name, items, request["platform"])
        )
        if not pending:
            locks.append(copy.deepcopy(chosen))
            return
        name = pending[0]
        for candidate in by_cover.get(name, []):
            if candidate["name"] in chosen:
                continue
            if not usable_for_group(candidate, current[name], request["platform"]):
                continue
            next_groups = copy.deepcopy(current)
            next_chosen = copy.deepcopy(chosen)
            next_chosen[candidate["name"]] = candidate
            for item in candidate["deps"]:
                add_item(next_groups, item)
            walk(next_groups, next_chosen)

    walk(groups, {})
    if not locks:
        return {
            "status": "blocked",
            "packages": [],
            "rejected": [{"name": item["name"], "reason": "no_lock"} for item in request["roots"]],
        }

    def rows(lock):
        return [lock[name] for name in sorted(lock)]

    def better(left, right):
        left_rows = rows(left)
        right_rows = rows(right)
        if len(left_rows) != len(right_rows):
            return len(left_rows) < len(right_rows)
        left_versions = [f"{item['name']}@{item['version']}" for item in left_rows]
        right_versions = [f"{item['name']}@{item['version']}" for item in right_rows]
        if left_versions != right_versions:
            return left_versions > right_versions
        return [item["hash"] for item in left_rows] < [item["hash"] for item in right_rows]

    best = locks[0]
    for lock in locks[1:]:
        if better(lock, best):
            best = lock
    return {
        "status": "ok",
        "packages": [
            {"name": item["name"], "version": item["version"], "hash": item["hash"]}
            for item in rows(best)
        ],
        "rejected": [],
    }


def write_case(request, registry):
    REQ.write_text(json.dumps(request, indent=2) + "\n")
    REG.write_text(json.dumps(registry, indent=2) + "\n")
    if OUT.exists():
        OUT.unlink()


def run_case(request, registry):
    write_case(request, registry)
    build = subprocess.run(
        [str(GO), "build", "./..."],
        cwd=APP,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    assert build.returncode == 0, build.stderr
    result = subprocess.run(
        [str(GO), "run", ".", str(REQ), str(REG), str(OUT)],
        cwd=APP,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert OUT.exists()
    return json.loads(OUT.read_text())


def assert_exact(actual, expected):
    assert set(actual) == {"status", "packages", "rejected"}
    assert isinstance(actual["packages"], list)
    assert isinstance(actual["rejected"], list)
    assert actual == expected


def test_public_fixture_has_expected_lock():
    """The public request requires platform, hash, feature, yanked, and transitive bounds together."""
    actual = run_case(copy.deepcopy(PUBLIC_REQUEST), copy.deepcopy(PUBLIC_REGISTRY))
    assert_exact(actual, expected_lock(PUBLIC_REQUEST, PUBLIC_REGISTRY))


def test_empty_roots_emit_empty_arrays():
    """An empty root list still writes ok status with packages and rejected as empty arrays."""
    request = {"platform": "linux-x64", "roots": []}
    registry = {"packages": [pkg("solo", "1.0.0")]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_bad_hash_removes_highest_candidate():
    """A version with an invalid hash is not usable even when its version is attractive."""
    request = {"platform": "linux-x64", "roots": [req("anchor", "1.0.0", True, None, False)]}
    registry = {"packages": [pkg("anchor", "2.0.0", bad=True), pkg("anchor", "1.5.0")]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_yanked_requires_every_accumulated_requirement_to_allow_it():
    """A yanked package is usable only when all requirements for that name allow it."""
    request = {"platform": "linux-x64", "roots": [req("kit", "1.0.0", True, None, False, [], True)]}
    registry = {"packages": [
        pkg("kit", "2.0.0", deps=[req("shared", "3.0.0", True, None, False, [], False)]),
        pkg("kit", "1.0.0", deps=[req("shared", "1.0.0", True, None, False, [], True)]),
        pkg("shared", "3.0.0", yanked=True),
        pkg("shared", "1.0.0"),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_feature_union_controls_candidate_selection():
    """Feature requirements gathered from different edges are accumulated per package name."""
    request = {"platform": "linux-x64", "roots": [
        req("left", "1.0.0", True, None, False),
        req("right", "1.0.0", True, None, False),
    ]}
    registry = {"packages": [
        pkg("left", "1.0.0", deps=[req("shared", "1.0.0", True, None, False, ["a"])]),
        pkg("right", "1.0.0", deps=[req("shared", "1.0.0", True, None, False, ["b"])]),
        pkg("shared", "2.0.0", features=["a"]),
        pkg("shared", "1.8.0", features=["a", "b"]),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_fewest_packages_beats_higher_version_list():
    """The first tie-break is complete lock size, before any version choice."""
    request = {"platform": "linux-x64", "roots": [req("gate", "1.0.0", True, None, False)]}
    registry = {"packages": [
        pkg("gate", "3.0.0", deps=[req("addon", "1.0.0", True, None, False)]),
        pkg("gate", "2.5.0"),
        pkg("addon", "1.0.0"),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_full_plan_version_list_sets_the_next_tie_break():
    """The lexicographic version-list comparison is made on the complete selected lock."""
    request = {"platform": "linux-x64", "roots": [req("alpha", "1.0.0", True, None, False)]}
    registry = {"packages": [
        pkg("alpha", "2.0.0", deps=[req("beta", "1.0.0", True, "2.0.0", False)]),
        pkg("alpha", "1.9.0", deps=[req("beta", "3.0.0", True, None, False)]),
        pkg("beta", "1.5.0"),
        pkg("beta", "3.4.0"),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_blocked_output_uses_root_order():
    """When no complete lock exists, all requested root names are rejected in request order."""
    request = {"platform": "linux-x64", "roots": [
        req("north", "2.0.0", True, None, False),
        req("south", "1.0.0", True, None, False),
    ]}
    registry = {"packages": [pkg("north", "1.0.0"), pkg("south", "1.0.0", bad=True)]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_later_dependency_can_invalidate_earlier_selection():
    """Requirements added after a package is selected still constrain that selected package."""
    request = {"platform": "linux-x64", "roots": [
        req("core", "1.0.0", True, None, False, ["tls"]),
        req("gate", "1.0.0", True, None, False),
    ]}
    registry = {"packages": [
        pkg("core", "3.2.0", ["linux-x64"], False, ["tls", "audit"]),
        pkg("core", "2.4.0", ["linux-x64"], False, ["tls", "audit"]),
        pkg("core", "1.8.0", ["linux-x64"], False, ["tls", "audit", "seal"]),
        pkg("gate", "2.0.0", ["linux-x64"], False, [], [
            req("core", "1.5.0", True, "2.0.0", False, ["seal"], False),
            req("leaf", "1.0.0", True, None, False),
        ]),
        pkg("gate", "1.5.0", ["linux-x64"], False, [], [
            req("core", "2.0.0", True, "3.0.0", False, ["audit"], False),
        ]),
        pkg("leaf", "1.0.0"),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_repeated_roots_accumulate_ranges_features_and_yanked_policy():
    """Repeated root requirements for the same name are all accumulated before selection."""
    request = {"platform": "linux-x64", "roots": [
        req("vault", "1.0.0", True, "4.0.0", False, ["seal"], True),
        req("vault", "2.0.0", False, "3.0.0", True, ["audit"], False),
    ]}
    registry = {"packages": [
        pkg("vault", "3.0.0", yanked=True, features=["seal", "audit"]),
        pkg("vault", "2.5.0", features=["seal"]),
        pkg("vault", "2.4.0", features=["seal", "audit"]),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_complete_lock_tie_break_ignores_candidate_order():
    """Equal-size locks use the sorted complete name@version list, not registry order."""
    request = {"platform": "linux-x64", "roots": [
        req("alpha", "1.0.0", True, None, False),
        req("gamma", "1.0.0", True, None, False),
    ]}
    registry = {"packages": [
        pkg("alpha", "2.0.0", deps=[req("beta", "1.0.0", True, "2.0.0", False)]),
        pkg("gamma", "2.0.0", deps=[req("beta", "1.0.0", True, "2.0.0", False)]),
        pkg("alpha", "1.9.0", deps=[req("beta", "3.0.0", True, None, False)]),
        pkg("gamma", "1.9.0", deps=[req("beta", "3.0.0", True, None, False)]),
        pkg("beta", "1.8.0"),
        pkg("beta", "3.4.0"),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_provider_package_can_satisfy_root_and_dependency_names():
    """A provided name can cover a root or dependency while output still uses the package's real name."""
    request = {"platform": "linux-x64", "roots": [
        req("client", "1.0.0", True, None, False),
        req("engine", "2.0.0", True, None, False, ["jit"]),
    ]}
    registry = {"packages": [
        pkg("client", "2.0.0", deps=[req("engine", "2.5.0", True, "4.0.0", False, ["jit"])]),
        pkg("engine", "3.0.0", features=["jit"], deps=[req("addon", "1.0.0", True, None, False)]),
        pkg("engine", "2.7.0", features=["jit"], deps=[req("addon", "1.0.0", True, None, False)]),
        pkg("shim", "1.4.0", features=["jit"], provides=[provide("engine", "3.2.0")]),
        pkg("addon", "1.0.0"),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_conflict_can_reject_a_locally_attractive_provider():
    """Directed conflicts are checked against another selected package's real or provided names."""
    request = {"platform": "linux-x64", "roots": [
        req("app", "1.0.0", True, None, False),
        req("runtime", "2.0.0", True, None, False),
    ]}
    registry = {"packages": [
        pkg("app", "3.0.0", deps=[req("guard", "1.0.0", True, None, False)]),
        pkg("guard", "1.0.0", provides=[provide("hazard", "1.0.0")]),
        pkg("fast", "9.0.0", features=["vm"], provides=[provide("runtime", "4.0.0")],
            conflicts=[req("hazard", "1.0.0", True, "2.0.0", False)]),
        pkg("steady", "2.5.0", features=["vm"], provides=[provide("runtime", "2.5.0")]),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_provided_requirement_names_accumulate_features_and_yanked_policy():
    """Feature and yanked checks accumulate by the requirement name satisfied through provides."""
    request = {"platform": "linux-x64", "roots": [
        req("api", "1.0.0", True, None, False, ["seal"], True),
        req("api", "1.0.0", True, None, False, ["audit"], False),
    ]}
    registry = {"packages": [
        pkg("adapter", "5.0.0", yanked=True, features=["seal", "audit"], provides=[provide("api", "3.0.0")]),
        pkg("adapter", "4.0.0", features=["seal"], provides=[provide("api", "2.8.0")]),
        pkg("adapter", "3.0.0", features=["seal", "audit"], provides=[provide("api", "2.4.0")]),
        pkg("api", "2.0.0", features=["seal"]),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def test_conflict_entries_ignore_features_and_allow_yanked_fields():
    """Conflict entries use the requirement name and range even when feature and yanked fields are populated."""
    request = {"platform": "linux-x64", "roots": [
        req("suite", "1.0.0", True, None, False),
        req("codec", "1.0.0", True, None, False),
    ]}
    registry = {"packages": [
        pkg("suite", "2.0.0", deps=[req("filter", "1.0.0", True, None, False)]),
        pkg("filter", "3.0.0", conflicts=[req("codec", "3.0.0", True, None, False, ["ignored"], True)]),
        pkg("codec", "3.2.0"),
        pkg("codec", "2.4.0"),
    ]}
    assert_exact(run_case(request, registry), expected_lock(request, registry))


def generated_case(index):
    platform = ["linux-x64", "linux-arm64", "darwin-arm64"][index % 3]
    upper = "4.0.0" if index % 4 else "3.0.0"
    allow = index % 5 == 0
    feature = "f" + str(index % 4)
    peer_feature = "p" + str(index % 3)
    shared_platform = [platform] if index % 6 else ["any"]
    request = {"platform": platform, "roots": [
        req("root", "1.0.0", True, upper, False, [feature], allow),
        req("peer", "1.0.0", True, None, False, [peer_feature]),
    ]}
    registry = {"packages": [
        pkg("root", "3.5.0", [platform], False, [feature], [
            req("shared", "2.0.0", True, "4.0.0", False, [feature], allow),
            req("bridge", "1.0.0", True, None, False),
        ]),
        pkg("root", "2.8.0", [platform], False, [feature], [
            req("shared", "1.0.0", True, "3.0.0", False, [], allow),
        ]),
        pkg("root", "2.4.0", ["linux-x64", "any"][index % 2:index % 2 + 1], False, [feature], []),
        pkg("peer", "2.0.0", ["any"], False, [peer_feature], [
            req("shared", "1.5.0", True, "3.5.0", False, [peer_feature if index % 2 else feature], allow),
        ]),
        pkg("peer", "1.7.0", [platform], False, [peer_feature], [
            req("shared", "2.2.0", True, "4.0.0", False, [], True),
        ]),
        pkg("bridge", "1.6.0", ["any"], False, [], [
            req("shared", "2.4.0", True, "3.0.0", False, [feature], allow),
        ]),
        pkg("shared", "3.2.0", shared_platform, index % 5 == 0, [feature, peer_feature]),
        pkg("shared", "2.8.0", [platform], False, [feature, peer_feature]),
        pkg("shared", "2.6.0", [platform], False, [feature]),
        pkg("shared", "2.2.0", [platform], False, [], bad=index % 7 == 0),
    ]}
    return request, registry


def test_generated_compatible_variants():
    """Generated variants combine documented platform, range, yanked, feature, hash, and tie-break rules."""
    for index in range(24):
        request, registry = generated_case(index)
        assert_exact(run_case(request, registry), expected_lock(request, registry))


def generated_provider_conflict_case(index):
    platform = ["linux-x64", "linux-arm64", "darwin-arm64"][index % 3]
    feature = "f" + str(index % 4)
    meter_feature = "m" + str(index % 3)
    allow_meter_yanked = index % 5 == 0
    upper = "4.0.0" if index % 4 else "3.3.0"
    request = {"platform": platform, "roots": [
        req("app", "2.0.0", True, None, False),
        req("meter", "1.0.0", True, None, False),
        req("engine", "2.0.0", True, upper, False, [feature], True),
    ]}
    registry = {"packages": [
        pkg("app", "3.0.0", [platform], False, [], [
            req("engine", "3.0.0", True, "4.0.0", False, [feature]),
            req("guard", "1.0.0", True, None, False),
        ]),
        pkg("app", "2.7.0", [platform], False, [], [
            req("engine", "2.4.0", True, "4.0.0", False, [feature]),
            req("bridge", "1.0.0", True, None, False),
        ]),
        pkg("meter", "2.0.0", ["any"], False, [meter_feature], [
            req("engine", "2.0.0", True, "3.6.0", False, [meter_feature], allow_meter_yanked),
        ]),
        pkg("meter", "1.6.0", [platform], False, [meter_feature], [
            req("engine", "3.0.0", True, "4.0.0", False, [], True),
        ]),
        pkg("guard", "1.0.0", ["any"], False, [], [], [provide("hazard", "1.0.0")]),
        pkg("bridge", "1.0.0", ["any"], False, [], []),
        pkg("native", "9.0.0", [platform], False, [feature, meter_feature],
            [], [provide("engine", "3.4.0")], [req("hazard", "1.0.0", True, None, False)]),
        pkg("shim", "5.0.0", [platform], index % 6 == 0, [feature, meter_feature],
            [], [provide("engine", "3.2.0")]),
        pkg("engine", "3.5.0", [platform], False, [feature],
            [], [], [req("meter", "2.0.0", True, None, False)]),
        pkg("engine", "3.1.0", [platform], False, [feature, meter_feature], [], [], [], index % 7 == 0),
        pkg("engine", "2.8.0", [platform], False, [feature, meter_feature]),
    ]}
    if index % 2:
        registry["packages"].append(
            pkg("meter", "2.4.0", [platform], False, [meter_feature], [
                req("engine", "2.5.0", True, "3.3.0", True, [feature, meter_feature], False),
            ])
        )
    if index % 3 == 0:
        registry["packages"].append(
            pkg("compat", "7.0.0", [platform], False, [feature, meter_feature],
                [], [provide("engine", "2.9.0")])
        )
    return request, registry


def test_generated_provider_and_conflict_variants():
    """Generated variants combine providers, conflicts, accumulated features, yanked policy, and tie-breaks."""
    for index in range(30):
        request, registry = generated_provider_conflict_case(index)
        assert_exact(run_case(request, registry), expected_lock(request, registry))

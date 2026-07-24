import json
import sys

# Reward is granted only when pytest exited cleanly AND the CTRF report shows a
# genuine run: at least one test collected, every test passed, nothing failed or
# errored. This defeats a collect-only trick (pytest exits 0 having run zero
# tests) because total would be 0.
pytest_rc = int(sys.argv[1]) if len(sys.argv) > 1 else 1

try:
    with open("/logs/verifier/ctrf.json") as f:
        data = json.load(f)
    summary = data["results"]["summary"]
    total = summary.get("tests", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    other = summary.get("other", 0)
    ok = pytest_rc == 0 and total > 0 and passed == total and failed == 0 and other == 0
except Exception:  # noqa: BLE001 -- intentional fail-closed on any parse error
    ok = False

sys.exit(0 if ok else 1)

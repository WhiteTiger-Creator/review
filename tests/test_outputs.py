import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

PERIODCTL = "/app/src/periodctl"
DATA_DIR = Path("/app/data")
JOURNALS = DATA_DIR / "journals"
CHART = DATA_DIR / "chart.tsv"
WINDOW = DATA_DIR / "window.json"
ETC_WINDOW = Path("/etc/period-close/window.json")
SBIN_LINK = Path("/usr/local/sbin/periodctl")
SYSTEMD_UNIT = Path("/etc/systemd/system/period-close.service")
VAR_LIB = Path("/var/lib/period-close")
LOCKFILE = Path("/tmp/periodctl.lock")

EXPECTED_LINES = [
    "CA-1000;53000;DR",
    "CA-2000;8000;CR",
    "EQ-3000;15000;CR",
    "EXP-5000;20000;DR",
    "REV-4000;50000;CR",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_periodctl(
    snapshot_path: Path,
    postings_dir: Path = JOURNALS,
    accounts: Path = CHART,
    window: Path = WINDOW,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            PERIODCTL,
            "--postings",
            str(postings_dir),
            "--accounts",
            str(accounts),
            "--window",
            str(window),
            "--snapshot",
            str(snapshot_path),
        ],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def data_hashes():
    hashes = {}
    for path in DATA_DIR.rglob("*"):
        if path.is_file():
            hashes[str(path.relative_to(DATA_DIR))] = sha256_file(path)
    return hashes


def _mode(path: Path) -> str:
    return oct(path.stat().st_mode & 0o777)


def test_periodctl_binary_mode_0755():
    """Verify /app/src/periodctl exists and has executable mode 0755."""
    assert Path(PERIODCTL).is_file()
    assert _mode(Path(PERIODCTL)) == "0o755"


def test_sbin_periodctl_symlink():
    """Verify /usr/local/sbin/periodctl is a symlink to /app/src/periodctl."""
    assert SBIN_LINK.is_symlink()
    assert SBIN_LINK.resolve() == Path(PERIODCTL).resolve()


def test_etc_window_installed():
    """Verify /etc/period-close/window.json is a byte-identical install with mode 0644."""
    assert ETC_WINDOW.is_file()
    assert ETC_WINDOW.read_bytes() == WINDOW.read_bytes()
    assert _mode(ETC_WINDOW) == "0o644"


def test_var_lib_period_close_mode_0755():
    """Verify /var/lib/period-close exists as a directory with mode 0755."""
    assert VAR_LIB.is_dir()
    assert _mode(VAR_LIB) == "0o755"


def test_systemd_unit_mode_and_targets():
    """Verify period-close.service is mode 0644 and references correct paths."""
    assert SYSTEMD_UNIT.is_file()
    assert _mode(SYSTEMD_UNIT) == "0o644"
    text = SYSTEMD_UNIT.read_text(encoding="utf-8")
    assert "/usr/local/sbin/periodctl" in text
    assert "/etc/period-close/window.json" in text
    assert "/var/lib/period-close/snapshot.tsv" in text
    assert "Type=oneshot" in text


def test_etc_window_path_produces_same_snapshot(tmp_path):
    """Verify snapshots match whether --window points at data or etc install."""
    via_data = tmp_path / "from_data.txt"
    via_etc = tmp_path / "from_etc.txt"
    code_data = run_periodctl(via_data, window=WINDOW).returncode
    code_etc = run_periodctl(via_etc, window=ETC_WINDOW).returncode
    assert code_data == code_etc == 1
    assert via_data.read_text(encoding="utf-8") == via_etc.read_text(encoding="utf-8")


def test_exit_code_with_unknown_account(tmp_path):
    """Verify unknown in-window accounts yield exit code 1."""
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot)
    assert result.returncode == 1, result.stderr


def test_snapshot_line_count(tmp_path):
    """Verify the shipped journals produce exactly five snapshot rows."""
    snapshot = tmp_path / "snapshot.tsv"
    run_periodctl(snapshot)
    lines = snapshot.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5


def test_snapshot_exact_content(tmp_path):
    """Verify snapshot lines match expected account balances and sides."""
    snapshot = tmp_path / "snapshot.tsv"
    run_periodctl(snapshot)
    lines = snapshot.read_text(encoding="utf-8").splitlines()
    assert lines == EXPECTED_LINES


def test_snapshot_schema(tmp_path):
    """Verify each snapshot line has ACCOUNT_ID;positive_cents;DR|CR format."""
    snapshot = tmp_path / "snapshot.tsv"
    run_periodctl(snapshot)
    for line in snapshot.read_text(encoding="utf-8").splitlines():
        account_id, balance, side = line.split(";")
        assert account_id
        assert balance.isdigit()
        assert int(balance) > 0
        assert side in {"DR", "CR"}


def test_case_insensitive_account_resolution(tmp_path):
    """Verify journal account IDs resolve to canonical chart IDs case-insensitively."""
    snapshot = tmp_path / "snapshot.tsv"
    run_periodctl(snapshot)
    text = snapshot.read_text(encoding="utf-8")
    assert "CA-1000;53000;DR" in text
    assert "EQ-3000;15000;CR" in text
    assert "ca-1000" not in text
    assert "eq-3000" not in text


def test_out_of_window_entries_excluded(tmp_path):
    """Verify postings outside the fiscal window do not affect balances."""
    snapshot = tmp_path / "snapshot.tsv"
    run_periodctl(snapshot)
    text = snapshot.read_text(encoding="utf-8")
    cash_balance = int(
        [line for line in text.splitlines() if line.startswith("CA-1000;")][0].split(";")[1]
    )
    assert cash_balance == 53000


def test_sort_order_case_insensitive(tmp_path):
    """Verify snapshot rows are sorted by account ID case-insensitively."""
    snapshot = tmp_path / "snapshot.tsv"
    run_periodctl(snapshot)
    account_ids = [line.split(";")[0] for line in snapshot.read_text(encoding="utf-8").splitlines()]
    assert account_ids == sorted(account_ids, key=str.casefold)


def test_window_boundary_dates_inclusive(tmp_path):
    """Verify start_date and end_date boundary postings are included in the window."""
    postings = tmp_path / "postings"
    postings.mkdir()
    (postings / "boundary.csv").write_text(
        "posting_date,account_id,debit_cents,credit_cents,memo\n"
        "2025-01-01,CA-1000,100,0,start boundary\n"
        "2025-01-01,REV-4000,0,100,start boundary\n"
        "2025-03-31,CA-1000,0,200,end boundary\n"
        "2025-03-31,EXP-5000,200,0,end boundary\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot, postings_dir=postings)
    assert result.returncode == 0, result.stderr
    lines = {line.split(";")[0]: line for line in snapshot.read_text(encoding="utf-8").splitlines()}
    assert lines["CA-1000"] == "CA-1000;100;CR"
    assert lines["REV-4000"] == "REV-4000;100;CR"
    assert lines["EXP-5000"] == "EXP-5000;200;DR"


def test_deterministic_output(tmp_path):
    """Verify repeated runs produce identical snapshots and exit codes."""
    first = tmp_path / "first.tsv"
    second = tmp_path / "second.tsv"
    code_one = run_periodctl(first).returncode
    code_two = run_periodctl(second).returncode
    assert code_one == code_two == 1
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_data_files_not_modified(data_hashes):
    """Verify periodctl does not modify files under /app/data/."""
    snapshot = Path(tempfile.mkdtemp()) / "snapshot.tsv"
    run_periodctl(snapshot)
    for path in DATA_DIR.rglob("*"):
        if path.is_file():
            rel = str(path.relative_to(DATA_DIR))
            assert sha256_file(path) == data_hashes[rel]


def test_exit_code_all_clean(tmp_path):
    """Verify a balanced window with no unknown accounts yields exit code 0."""
    postings = tmp_path / "clean"
    postings.mkdir()
    shutil.copytree(JOURNALS, postings, dirs_exist_ok=True)
    (postings / "legacy.csv").write_text(
        "posting_date,account_id,debit_cents,credit_cents,memo\n"
        "2025-03-15,EQ-3000,0,15000,Owner draw\n"
        "2025-03-15,CA-1000,15000,0,Cash transfer for draw\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot, postings_dir=postings)
    assert result.returncode == 0, result.stderr


def test_zero_balance_excluded(tmp_path):
    """Verify accounts whose net balance is zero are omitted from the snapshot."""
    postings = tmp_path / "postings"
    postings.mkdir()
    (postings / "zero.csv").write_text(
        "posting_date,account_id,debit_cents,credit_cents,memo\n"
        "2025-02-01,CA-1000,5000,0,payment\n"
        "2025-02-01,REV-4000,0,5000,revenue\n"
        "2025-02-15,CA-1000,0,5000,refund\n"
        "2025-02-15,REV-4000,5000,0,rev reversal\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot, postings_dir=postings)
    assert result.returncode == 0
    assert snapshot.read_text(encoding="utf-8").strip() == ""


def test_exit_code_unbalanced_journals(tmp_path):
    """Verify unbalanced in-window postings yield exit code 1."""
    postings = tmp_path / "bad"
    postings.mkdir()
    (postings / "skew.csv").write_text(
        "posting_date,account_id,debit_cents,credit_cents,memo\n"
        "2025-02-10,CA-1000,5000,0,orphan debit\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot, postings_dir=postings)
    assert result.returncode == 1, result.stderr


def test_exit_code_invalid_arguments(tmp_path):
    """Verify missing required CLI arguments yield exit code 2."""
    snapshot = tmp_path / "snapshot.tsv"
    result = subprocess.run(
        [PERIODCTL, "--postings", str(JOURNALS), "--snapshot", str(snapshot)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2


def test_exit_code_unreadable_accounts_path(tmp_path):
    """Verify unreadable but existing accounts path yields exit code 2."""
    unreadable = tmp_path / "locked.tsv"
    unreadable.write_text("account_id\tname\ttype\tnormal_balance\n", encoding="utf-8")
    unreadable.chmod(0o000)
    snapshot = tmp_path / "snapshot.tsv"
    try:
        result = run_periodctl(snapshot, accounts=unreadable)
        assert result.returncode == 2
    finally:
        unreadable.chmod(0o644)


def test_whitespace_trimmed_and_blank_lines_ignored(tmp_path):
    """Verify whitespace is trimmed and blank journal lines are ignored."""
    postings = tmp_path / "postings"
    postings.mkdir()
    (postings / "messy.csv").write_text(
        "posting_date,account_id,debit_cents,credit_cents,memo\n"
        "\n"
        "2025-02-03,  ca-1000  , 700 , 0 ,cash receipt\n"
        "2025-02-03, REV-4000 ,0, 700 , revenue booking\n"
        "\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot, postings_dir=postings)
    assert result.returncode == 0, result.stderr
    assert snapshot.read_text(encoding="utf-8").splitlines() == [
        "CA-1000;700;DR",
        "REV-4000;700;CR",
    ]


def test_invalid_in_window_rows_fail_but_valid_rows_still_snapshot(tmp_path):
    """Verify invalid rows fail the run but valid known-account rows still appear."""
    postings = tmp_path / "postings"
    postings.mkdir()
    (postings / "mixed.csv").write_text(
        "posting_date,account_id,debit_cents,credit_cents,memo\n"
        "2025-02-10,CA-1000,700,0,valid debit\n"
        "2025-02-10,REV-4000,0,700,valid credit\n"
        "2025-02-11,CA-1000,10,10,both sides set\n"
        "2025-02-12,EXP-5000,foo,0,non numeric debit\n"
        "2025-02-13,CA-1000,-5,0,negative debit\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot, postings_dir=postings)
    assert result.returncode == 1, result.stderr
    assert snapshot.read_text(encoding="utf-8").splitlines() == [
        "CA-1000;700;DR",
        "REV-4000;700;CR",
    ]


def test_both_sides_zero_row_is_invalid(tmp_path):
    """Verify rows with both debit and credit zero fail the run with exit code 1."""
    postings = tmp_path / "postings"
    postings.mkdir()
    (postings / "zero_sides.csv").write_text(
        "posting_date,account_id,debit_cents,credit_cents,memo\n"
        "2025-02-10,CA-1000,700,0,valid debit\n"
        "2025-02-10,REV-4000,0,700,valid credit\n"
        "2025-02-11,CA-1000,0,0,both sides zero\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot, postings_dir=postings)
    assert result.returncode == 1, result.stderr
    assert snapshot.read_text(encoding="utf-8").splitlines() == [
        "CA-1000;700;DR",
        "REV-4000;700;CR",
    ]


def test_duplicate_chart_ids_case_insensitive_fail_with_empty_snapshot(tmp_path):
    """Verify case-insensitive duplicate chart IDs fail with exit 1 and empty snapshot."""
    chart = tmp_path / "chart.tsv"
    chart.write_text(
        "account_id\tname\ttype\tnormal_balance\n"
        "\n"
        "CA-1000\tCash\tasset\tdebit\n"
        "ca-1000\tDuplicate Cash\tasset\tdebit\n"
        "REV-4000\tRevenue\trevenue\tcredit\n",
        encoding="utf-8",
    )
    postings = tmp_path / "postings"
    postings.mkdir()
    (postings / "simple.csv").write_text(
        "posting_date,account_id,debit_cents,credit_cents,memo\n"
        "2025-02-14,CA-1000,900,0,cash sale\n"
        "2025-02-14,REV-4000,0,900,revenue\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot, postings_dir=postings, accounts=chart)
    assert result.returncode == 1, result.stderr
    assert snapshot.read_text(encoding="utf-8") == ""


def test_lockfile_concurrency_and_cleanup(tmp_path):
    """Verify sequential runs succeed and the lockfile is cleaned up after each run."""
    snapshot1 = tmp_path / "snapshot1.tsv"
    res1 = run_periodctl(snapshot1)
    assert res1.returncode == 1
    assert not LOCKFILE.exists()

    snapshot2 = tmp_path / "snapshot2.tsv"
    res2 = run_periodctl(snapshot2)
    assert res2.returncode == 1
    assert not LOCKFILE.exists()

    res3 = subprocess.run([PERIODCTL], capture_output=True, text=True)
    assert res3.returncode == 2

    snapshot3 = tmp_path / "snapshot3.tsv"
    res4 = run_periodctl(snapshot3)
    assert res4.returncode == 1
    assert not LOCKFILE.exists()


def test_stale_lockfile_dead_pid_takes_over(tmp_path):
    """Verify periodctl takes over when lockfile holds a dead PID."""
    LOCKFILE.write_text("99999999", encoding="utf-8")
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot)
    assert result.returncode == 1
    assert not LOCKFILE.exists()


def test_active_lockfile_pid_blocks_run(tmp_path):
    """Verify periodctl exits 1 when lockfile holds an active PID."""
    LOCKFILE.write_text(str(os.getpid()), encoding="utf-8")
    snapshot = tmp_path / "snapshot.tsv"
    try:
        result = run_periodctl(snapshot)
        assert result.returncode == 1
    finally:
        LOCKFILE.unlink(missing_ok=True)


def test_path_with_spaces(tmp_path):
    """Verify CLI handles postings directories whose paths contain spaces."""
    postings = tmp_path / "postings folder with spaces"
    postings.mkdir()
    (postings / "clean.csv").write_text(
        "posting_date,account_id,debit_cents,credit_cents,memo\n"
        "2025-02-01,CA-1000,100,0,payment\n"
        "2025-02-01,REV-4000,0,100,revenue\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot, postings_dir=postings)
    assert result.returncode == 0, result.stderr
    lines = snapshot.read_text(encoding="utf-8").splitlines()
    assert lines == [
        "CA-1000;100;DR",
        "REV-4000;100;CR",
    ]


def test_memo_field_with_commas(tmp_path):
    """Verify quoted memo fields containing commas are parsed correctly."""
    postings = tmp_path / "postings"
    postings.mkdir()
    (postings / "comma_memo.csv").write_text(
        "posting_date,account_id,debit_cents,credit_cents,memo\n"
        '2025-02-01,CA-1000,150,0,"payment, partial"\n'
        '2025-02-01,REV-4000,0,150,"revenue, deferred"\n',
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.tsv"
    result = run_periodctl(snapshot, postings_dir=postings)
    assert result.returncode == 0, result.stderr
    lines = snapshot.read_text(encoding="utf-8").splitlines()
    assert lines == [
        "CA-1000;150;DR",
        "REV-4000;150;CR",
    ]

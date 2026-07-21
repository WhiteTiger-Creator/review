import glob
import hashlib
import os
import time
import requests

BASE = "http://localhost:8080"

# Raw SHA256 of /app/api_contract.json as shipped — checked as raw bytes so
# that 2-space indentation and the required single trailing newline are enforced.
_API_CONTRACT_HASH = "f76a62ce9dfd0a3acbc47c5847bed3da9e36001c7e4b827efdc41135863a5b02"

# Scripts that existed in /app at image-build time; they are not bypass artefacts.
_PREEXISTING_SCRIPTS = {"/app/healthcheck.sh"}


class TestJobCreation:
    def test_create_job_returns_201(self):
        """POST /jobs with valid fields must return 201 (not 200)."""
        r = requests.post(f"{BASE}/jobs", json={
            "type": "email",
            "payload": '{"to":"test@example.com"}',
            "priority": 1
        })
        assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["status"] == "pending"
        assert data["type"] == "email"
        assert data["priority"] == 1

    def test_create_job_stores_payload_correctly(self):
        """payload field must be round-tripped exactly as submitted."""
        payload = '{"report_id":"test-42","format":"csv"}'
        r = requests.post(f"{BASE}/jobs", json={"type": "report", "payload": payload})
        assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
        assert r.json()["payload"] == payload, \
            f"payload mismatch: {r.json().get('payload')!r}"

    def test_create_job_missing_type_returns_400(self):
        """POST /jobs without 'type' returns 400."""
        r = requests.post(f"{BASE}/jobs", json={"payload": "x", "priority": 0})
        assert r.status_code == 400, f"expected 400, got {r.status_code}"

    def test_create_job_default_priority_is_zero(self):
        """Omitting priority field yields priority=0 in response."""
        r = requests.post(f"{BASE}/jobs", json={"type": "notification"})
        assert r.status_code == 201
        assert r.json()["priority"] == 0

    def test_create_job_worker_id_is_null_on_creation(self):
        """Newly created jobs have worker_id=null (not yet dispatched)."""
        r = requests.post(f"{BASE}/jobs", json={"type": "image_resize"})
        assert r.status_code == 201
        assert r.json()["worker_id"] is None


class TestListJobs:
    def test_list_all_jobs_returns_at_least_six_seeded(self):
        """GET /jobs returns the six seeded jobs plus any created by earlier tests."""
        r = requests.get(f"{BASE}/jobs")
        assert r.status_code == 200
        jobs = r.json()
        assert isinstance(jobs, list)
        assert len(jobs) >= 6

    def test_list_jobs_filtered_by_status_pending(self):
        """GET /jobs?status=pending returns only pending jobs."""
        r = requests.get(f"{BASE}/jobs?status=pending")
        assert r.status_code == 200
        jobs = r.json()
        assert all(j["status"] == "pending" for j in jobs), \
            f"non-pending job in result: {[j['status'] for j in jobs]}"

    def test_list_jobs_filtered_by_status_completed(self):
        """GET /jobs?status=completed returns only completed jobs (includes seed job 1)."""
        r = requests.get(f"{BASE}/jobs?status=completed")
        assert r.status_code == 200
        jobs = r.json()
        assert all(j["status"] == "completed" for j in jobs)
        ids = [j["id"] for j in jobs]
        assert 1 in ids, f"seeded completed job (id=1) not found in {ids}"

    def test_list_jobs_filtered_by_status_failed(self):
        """GET /jobs?status=failed returns only failed jobs (includes seed job 5)."""
        r = requests.get(f"{BASE}/jobs?status=failed")
        assert r.status_code == 200
        jobs = r.json()
        assert all(j["status"] == "failed" for j in jobs)
        ids = [j["id"] for j in jobs]
        assert 5 in ids, f"seeded failed job (id=5) not found in {ids}"

    def test_get_job_by_id(self):
        """GET /jobs/1 returns the correct seeded job."""
        r = requests.get(f"{BASE}/jobs/1")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == 1
        assert data["type"] == "email"
        assert data["status"] == "completed"
        assert data["priority"] == 5

    def test_get_job_not_found_returns_404(self):
        """GET /jobs/9999 returns 404."""
        r = requests.get(f"{BASE}/jobs/9999")
        assert r.status_code == 404


class TestJobWorkerName:
    def test_running_job_has_worker_name_populated(self):
        """GET /jobs/2 (seeded as running, worker_id=2='worker-beta') must include worker_name='worker-beta'."""
        r = requests.get(f"{BASE}/jobs/2")
        assert r.status_code == 200
        data = r.json()
        assert data["worker_id"] == 2, \
            f"expected worker_id=2, got {data.get('worker_id')!r}"
        assert data["worker_name"] == "worker-beta", \
            f"expected worker_name='worker-beta', got {data.get('worker_name')!r}"

    def test_completed_job_has_worker_name_populated(self):
        """GET /jobs/1 (seeded as completed, worker_id=1='worker-alpha') must include worker_name."""
        r = requests.get(f"{BASE}/jobs/1")
        assert r.status_code == 200
        data = r.json()
        assert data["worker_name"] == "worker-alpha", \
            f"expected worker_name='worker-alpha', got {data.get('worker_name')!r}"

    def test_pending_job_has_empty_worker_name(self):
        """GET /jobs/3 (seeded as pending, no worker) must have worker_id=null and empty worker_name."""
        r = requests.get(f"{BASE}/jobs/3")
        assert r.status_code == 200
        data = r.json()
        assert data["worker_id"] is None
        assert data["worker_name"] == ""


class TestCancelJob:
    def test_cancel_pending_job_returns_200(self):
        """POST /jobs/:id/cancel on a pending job returns 200 with status='cancelled'."""
        # Create a fresh pending job so we don't disturb seeded data
        job = requests.post(f"{BASE}/jobs", json={"type": "test_cancel", "priority": 0}).json()
        job_id = job["id"]

        r = requests.post(f"{BASE}/jobs/{job_id}/cancel")
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        assert r.json()["status"] == "cancelled"

    def test_cancel_running_job_returns_409(self):
        """POST /jobs/2/cancel (seeded as running) must return 409."""
        r = requests.post(f"{BASE}/jobs/2/cancel")
        assert r.status_code == 409, f"expected 409 for running job, got {r.status_code}"

    def test_cancel_completed_job_returns_409(self):
        """POST /jobs/1/cancel (seeded as completed) must return 409."""
        r = requests.post(f"{BASE}/jobs/1/cancel")
        assert r.status_code == 409, f"expected 409 for completed job, got {r.status_code}"

    def test_cancel_failed_job_returns_409(self):
        """POST /jobs/5/cancel (seeded as failed) must return 409."""
        r = requests.post(f"{BASE}/jobs/5/cancel")
        assert r.status_code == 409, f"expected 409 for failed job, got {r.status_code}"

    def test_cancel_nonexistent_job_returns_404(self):
        """POST /jobs/9999/cancel returns 404."""
        r = requests.post(f"{BASE}/jobs/9999/cancel")
        assert r.status_code == 404

    def test_cancelled_job_stays_cancelled(self):
        """A cancelled job must remain cancelled after 5 seconds (re-checked after a delay)."""
        job = requests.post(f"{BASE}/jobs", json={"type": "durable_cancel_check"}).json()
        job_id = job["id"]

        cancel_r = requests.post(f"{BASE}/jobs/{job_id}/cancel")
        assert cancel_r.status_code == 200, \
            f"cancel failed (check cancel guard bug): {cancel_r.status_code} {cancel_r.text}"

        # Verify immediately
        assert requests.get(f"{BASE}/jobs/{job_id}").json()["status"] == "cancelled"

        # Wait long enough for the config watcher to fire at least once (watcher interval = 3s)
        time.sleep(5)

        final = requests.get(f"{BASE}/jobs/{job_id}").json()
        assert final["status"] == "cancelled", \
            f"job reverted from cancelled to '{final['status']}' after 5 s — " \
            f"something is changing the job status after cancellation"


class TestJobLifecycle:
    def test_complete_running_job(self):
        """POST /jobs/2/complete (seeded as running) returns 200 with status='completed'."""
        r = requests.post(f"{BASE}/jobs/2/complete")
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        assert r.json()["status"] == "completed"

    def test_complete_pending_job_returns_409(self):
        """POST /jobs/:id/complete on a pending job returns 409."""
        job = requests.post(f"{BASE}/jobs", json={"type": "cant_complete_pending"}).json()
        r = requests.post(f"{BASE}/jobs/{job['id']}/complete")
        assert r.status_code == 409, f"expected 409, got {r.status_code}"

    def test_fail_nonexistent_job_returns_404(self):
        """POST /jobs/9999/fail returns 404."""
        r = requests.post(f"{BASE}/jobs/9999/fail")
        assert r.status_code == 404


class TestWorkers:
    def test_list_workers_returns_three_seeded(self):
        """GET /workers returns at least the 3 seeded workers."""
        r = requests.get(f"{BASE}/workers")
        assert r.status_code == 200
        workers = r.json()
        assert len(workers) >= 3
        names = [w["name"] for w in workers]
        assert "worker-alpha" in names
        assert "worker-beta" in names
        assert "worker-gamma" in names

    def test_register_worker_returns_201(self):
        """POST /workers/register returns 201 with the new worker."""
        r = requests.post(f"{BASE}/workers/register", json={"name": "worker-delta"})
        assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["name"] == "worker-delta"
        assert data["id"] is not None

    def test_register_worker_missing_name_returns_400(self):
        """POST /workers/register without name returns 400."""
        r = requests.post(f"{BASE}/workers/register", json={})
        assert r.status_code == 400


class TestStats:
    def test_get_stats_returns_expected_shape(self):
        """GET /stats returns all five status counters."""
        r = requests.get(f"{BASE}/stats")
        assert r.status_code == 200
        data = r.json()
        for key in ("pending", "running", "completed", "failed", "cancelled"):
            assert key in data, f"missing key '{key}' in stats response"
            assert isinstance(data[key], int)

    def test_stats_completed_count_is_at_least_one(self):
        """Seeded data has job 1 as completed, so completed >= 1."""
        r = requests.get(f"{BASE}/stats")
        assert r.status_code == 200
        assert r.json()["completed"] >= 1


class TestWorkerPool:
    def test_pending_job_gets_processed_automatically(self):
        """The background worker pool must automatically pick up pending jobs and process them.

        The pool polls every 500 ms and takes ~2 s to process each job.
        We wait up to 10 s for the job to move out of 'pending' status.
        """
        r = requests.post(f"{BASE}/jobs", json={"type": "auto_process_test", "priority": 0})
        assert r.status_code == 201
        job_id = r.json()["id"]

        deadline = time.time() + 10
        while time.time() < deadline:
            status = requests.get(f"{BASE}/jobs/{job_id}").json()["status"]
            if status in ("running", "completed"):
                return
            time.sleep(0.5)

        final = requests.get(f"{BASE}/jobs/{job_id}").json()
        assert final["status"] in ("running", "completed"), (
            f"Worker pool did not pick up job {job_id} within 10 s; "
            f"still '{final['status']}'. Check that the background worker goroutine is running."
        )


class TestFileIntegrity:
    def test_api_contract_not_modified(self):
        """api_contract.json must not be modified — verified via raw SHA256, not parsed JSON.

        Hashing raw bytes (not json.loads output) ensures that the required 2-space
        indentation and single trailing newline are also enforced, not just the content.
        """
        path = "/app/api_contract.json"
        with open(path, "rb") as f:
            raw = f.read()
        actual = hashlib.sha256(raw).hexdigest()
        assert actual == _API_CONTRACT_HASH, (
            "api_contract.json was modified (raw bytes differ from original).\n"
            "Restore the file exactly as provided — including 2-space indentation "
            "and the single trailing newline."
        )

    def test_no_bypass_scripts_added(self):
        """The fix must be in Go source — no script files should be added to /app.

        Checking only for .py files is insufficient; this test catches any scripting
        language (Python, Ruby, shell, Perl, JavaScript, etc.) that an agent might
        use to bypass fixing the Go source code.
        """
        script_exts = {".py", ".rb", ".sh", ".pl", ".js", ".ts", ".bash", ".zsh", ".php"}
        found = [
            p for p in glob.glob("/app/*")
            if os.path.isfile(p)
            and os.path.splitext(p)[1] in script_exts
            and p not in _PREEXISTING_SCRIPTS
        ]
        assert not found, (
            f"Non-Go script files found in /app: {found}. "
            "The solution must fix the Go source files directly, not add bypass scripts."
        )

## Summary of Runs for "tbench-task"
### Difficulty: medium
| Agent/Model | # of total runs | # of successes | # of failures<br>(agent timeout) | # of failures<br>(other reasons) | Accuracy |
|-------------|-----------------|-----------------|------------------------------------|---------------|----------|
| nop | 1 | 0 | 0 | 1 | 0.0 |
| oracle | 3 | 3 | 0 | 0 | 1.0 |
| terminus-claude-opus-4-6 | 5 | 5 | 0 | 0 | 1.0 |
| terminus-gpt5-2 | 5 | 2 | 0 | 3 | 0.4 |
<details>
<summary>Tests Result</summary>

✅ This task is solvable by the agents.
| Test Name | Successful Runs / Total Runs |
|-------------|------------------------------|
| TestJobCreation → test_create_job_returns_201 | 10 / 10 |
| TestJobCreation → test_create_job_stores_payload_correctly | 10 / 10 |
| TestJobCreation → test_create_job_missing_type_returns_400 | 10 / 10 |
| TestJobCreation → test_create_job_default_priority_is_zero | 10 / 10 |
| TestJobCreation → test_create_job_worker_id_is_null_on_creation | 10 / 10 |
| TestListJobs → test_list_all_jobs_returns_at_least_six_seeded | 10 / 10 |
| TestListJobs → test_list_jobs_filtered_by_status_pending | 7 / 10 |
| TestListJobs → test_list_jobs_filtered_by_status_completed | 7 / 10 |
| TestListJobs → test_list_jobs_filtered_by_status_failed | 7 / 10 |
| TestListJobs → test_get_job_by_id | 8 / 10 |
| TestListJobs → test_get_job_not_found_returns_404 | 10 / 10 |
| TestJobWorkerName → test_running_job_has_worker_name_populated | 8 / 10 |
| TestJobWorkerName → test_completed_job_has_worker_name_populated | 8 / 10 |
| TestJobWorkerName → test_pending_job_has_empty_worker_name | 8 / 10 |
| TestCancelJob → test_cancel_pending_job_returns_200 | 8 / 10 |
| TestCancelJob → test_cancel_running_job_returns_409 | 10 / 10 |
| TestCancelJob → test_cancel_completed_job_returns_409 | 10 / 10 |
| TestCancelJob → test_cancel_failed_job_returns_409 | 10 / 10 |
| TestCancelJob → test_cancel_nonexistent_job_returns_404 | 10 / 10 |
| TestCancelJob → test_cancelled_job_stays_cancelled | 8 / 10 |
| TestJobLifecycle → test_complete_running_job | 8 / 10 |
| TestJobLifecycle → test_complete_pending_job_returns_409 | 10 / 10 |
| TestJobLifecycle → test_fail_nonexistent_job_returns_404 | 10 / 10 |
| TestWorkers → test_list_workers_returns_three_seeded | 10 / 10 |
| TestWorkers → test_register_worker_returns_201 | 10 / 10 |
| TestWorkers → test_register_worker_missing_name_returns_400 | 10 / 10 |
| TestStats → test_get_stats_returns_expected_shape | 10 / 10 |
| TestStats → test_stats_completed_count_is_at_least_one | 10 / 10 |
| TestWorkerPool → test_pending_job_gets_processed_automatically | 10 / 10 |
| TestFileIntegrity → test_api_contract_not_modified | 10 / 10 |
| TestFileIntegrity → test_no_bypass_scripts_added | 10 / 10 |
</details>

### Analysis on Agent Failures
| Check       | Outcome  | Explanation              |
|-------------|----------|--------------------------|
| Task Instruction Sufficiency | ✅ PASS | ## Job Summary

### 1. Overall Results

**0 of 3 trials passed** (all scored 0.0 reward). The scoring scheme appears binary or threshold-based — even tbench-task__zMFzNnG, which passed 28/31 tests, received no credit.

### 2. Common Failure Patterns

Two bugs were introduced (not inherited) by the agents, and they account for all failures:

**Bug A — Ambiguous SQL `status` column after LEFT JOIN** *(all 3 trials)*
Every agent added a `LEFT JOIN workers` to `ListJobs` to fetch `worker_name`, but failed to qualify the `WHERE status = ?` clause as `WHERE jobs.status = ?`. Since both the `jobs` and `workers` tables have a `status` column, SQLite returns a 500 on any filtered-list query. This single bug caused 3 test failures in every run.

**Bug B — Over-broad Perl substitution for HTTP status codes** *(tbench-task__gr3SdXV and tbench-task__HYVvkCR)*
Two agents used `perl -i -pe` to swap `http.StatusOK` → `http.StatusCreated` across the entire `handlers.go` file, instead of scoping the change to only the `createJob` handler. This incorrectly set GET `/jobs/:id`, POST `/cancel`, and POST `/complete` to return 201, causing 7 additional test failures. tbench-task__zMFzNnG avoided this mistake, which is why it reached 28/31.

### 3. Hack Check

**No cheating detected.** All three trials passed `reward_hacking`. Agents edited only source files (`main.go`, `handlers.go`, `service.go`), rebuilt via `make build`, and validated with `curl`. None accessed test files, wrote to reward files, or touched the `solution/` directory.

### 4. Instruction / Specification Issues

**None found.** All three trials passed `task_specification`. The instructions and `/app/api_contract.json` clearly specify every contract requirement the tests exercise. All failures trace back to agent implementation errors, not ambiguous or missing specs.

### 5. Progress (How Close Did Agents Get?)

| Trial | Tests Passed | Tests Failed | Gap to Pass |
|---|---|---|---|
| tbench-task__zMFzNnG | 28/31 | 3 | 1 bug (SQL ambiguity) |
| tbench-task__gr3SdXV | 21/31 | 10 | 2 bugs (SQL + regex) |
| tbench-task__HYVvkCR | 21/31 | 10 | 2 bugs (SQL + regex) |

tbench-task__zMFzNnG was one targeted fix away from a perfect score.

### 6. Key Differences Between Trials

The standout difference is **how each agent scoped the HTTP status code fix**:
- tbench-task__zMFzNnG surgically patched only `createJob` → 201, correctly leaving other handlers at 200.
- tbench-task__gr3SdXV and tbench-task__HYVvkCR both reached for a broad regex substitution, which mutated unrelated handlers and added 7 new failures on top of the shared SQL bug.

All three agents identified the correct set of bugs to fix (status codes, `requeueCancelledJobs`, `job_type` column, `worker_name` JOIN, stats `cancelled` field), but none correctly qualified the `jobs.status` column in the LEFT JOIN — making the SQL ambiguity the single most actionable fix to target for improvement. |
<!-- test-summary-end -->
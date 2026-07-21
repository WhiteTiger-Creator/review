## Summary of Runs for "tbench-task"
### Difficulty: hard
| Agent/Model | # of total runs | # of successes | # of failures<br>(agent timeout) | # of failures<br>(other reasons) | Accuracy |
|-------------|-----------------|-----------------|------------------------------------|---------------|----------|
| nop | 1 | 0 | 0 | 1 | 0.0 |
| oracle | 3 | 3 | 0 | 0 | 1.0 |
| terminus-claude-opus-4-6 | 5 | 5 | 0 | 0 | 1.0 |
| terminus-gpt5-2 | 5 | 0 | 0 | 5 | 0.0 |
<details>
<summary>Tests Result</summary>

✅ This task is solvable by the agents.
| Test Name | Successful Runs / Total Runs |
|-------------|------------------------------|
| milestone_1 → TestMilestone1 → test_server_binary_exists | 10 / 10 |
| milestone_1 → TestMilestone1 → test_server_binary_is_elf | 10 / 10 |
| milestone_1 → TestMilestone1 → test_server_responds_on_port_8080 | 10 / 10 |
| milestone_1 → TestMilestone1 → test_root_serves_html_page | 10 / 10 |
| milestone_1 → TestMilestone1 → test_css_stylesheet_is_served | 10 / 10 |
| milestone_1 → TestMilestone1 → test_javascript_file_is_served | 10 / 10 |
| milestone_1 → TestMilestone1 → test_html_contains_note_form | 10 / 10 |
| milestone_1 → TestMilestone1 → test_html_contains_title_input | 10 / 10 |
| milestone_1 → TestMilestone1 → test_html_contains_content_textarea | 10 / 10 |
| milestone_1 → TestMilestone1 → test_html_contains_submit_button | 10 / 10 |
| milestone_1 → TestMilestone1 → test_html_contains_notes_list_container | 10 / 10 |
| milestone_1 → TestMilestone1 → test_nonexistent_static_file_returns_404 | 10 / 10 |
| milestone_1 → TestMilestone1 → test_path_traversal_blocked | 10 / 10 |
| milestone_1 → TestMilestone1 → test_path_traversal_encoded_blocked | 10 / 10 |
| milestone_1 → TestMilestone1 → test_path_traversal_percent_encoded_dotdot_blocked | 10 / 10 |
| milestone_2 → TestMilestone2 → test_api_key_file_exists | 10 / 10 |
| milestone_2 → TestMilestone2 → test_api_key_read_from_file | 6 / 10 |
| milestone_2 → TestMilestone2 → test_database_file_at_expected_path | 10 / 10 |
| milestone_2 → TestMilestone2 → test_create_note_returns_201 | 6 / 10 |
| milestone_2 → TestMilestone2 → test_create_note_returns_id_field | 6 / 10 |
| milestone_2 → TestMilestone2 → test_create_note_echoes_title_and_content | 6 / 10 |
| milestone_2 → TestMilestone2 → test_create_note_missing_title_returns_400 | 9 / 10 |
| milestone_2 → TestMilestone2 → test_create_note_empty_body_returns_400 | 9 / 10 |
| milestone_2 → TestMilestone2 → test_get_all_notes_returns_array | 10 / 10 |
| milestone_2 → TestMilestone2 → test_get_all_notes_includes_created_note | 6 / 10 |
| milestone_2 → TestMilestone2 → test_get_single_note_by_id | 6 / 10 |
| milestone_2 → TestMilestone2 → test_get_nonexistent_note_returns_404 | 10 / 10 |
| milestone_2 → TestMilestone2 → test_update_note_changes_fields | 6 / 10 |
| milestone_2 → TestMilestone2 → test_update_note_empty_title_returns_400 | 6 / 10 |
| milestone_2 → TestMilestone2 → test_update_note_missing_title_returns_400 | 6 / 10 |
| milestone_2 → TestMilestone2 → test_update_nonexistent_note_returns_404 | 9 / 10 |
| milestone_2 → TestMilestone2 → test_delete_note_removes_it | 6 / 10 |
| milestone_2 → TestMilestone2 → test_delete_nonexistent_note_returns_404 | 9 / 10 |
| milestone_2 → TestMilestone2 → test_api_get_response_content_type_is_json | 10 / 10 |
| milestone_2 → TestMilestone2 → test_api_get_response_has_cors_header | 10 / 10 |
| milestone_2 → TestMilestone2 → test_api_options_preflight_returns_cors_allowlist | 10 / 10 |
| milestone_2 → TestMilestone2 → test_api_post_response_content_type_and_cors | 6 / 10 |
| milestone_2 → TestMilestone2 → test_api_put_response_content_type_and_cors | 6 / 10 |
| milestone_2 → TestMilestone2 → test_api_delete_response_content_type_and_cors | 6 / 10 |
| milestone_2 → TestMilestone2 → test_api_get_single_response_content_type_and_cors | 6 / 10 |
| milestone_2 → TestMilestone2 → test_error_responses_have_json_and_cors_headers | 7 / 10 |
| milestone_2 → TestMilestone2 → test_post_without_api_key_returns_401 | 10 / 10 |
| milestone_2 → TestMilestone2 → test_put_without_api_key_returns_401 | 6 / 10 |
| milestone_2 → TestMilestone2 → test_delete_without_api_key_returns_401 | 6 / 10 |
| milestone_2 → TestMilestone2 → test_wrong_api_key_returns_401 | 10 / 10 |
| milestone_2 → TestMilestone2 → test_put_wrong_api_key_returns_401 | 6 / 10 |
| milestone_2 → TestMilestone2 → test_delete_wrong_api_key_returns_401 | 6 / 10 |
| milestone_2 → TestMilestone2 → test_get_without_api_key_succeeds | 10 / 10 |
| milestone_2 → TestMilestone2 → test_get_single_note_without_api_key_succeeds | 6 / 10 |
| milestone_2 → TestMilestone2 → test_pagination_limit_returns_correct_count | 6 / 10 |
| milestone_2 → TestMilestone2 → test_pagination_offset_skips_notes | 6 / 10 |
| milestone_2 → TestMilestone2 → test_pagination_x_total_count_header | 6 / 10 |
| milestone_2 → TestMilestone2 → test_pagination_default_limit_is_50 | 6 / 10 |
| milestone_2 → TestMilestone2 → test_pagination_max_limit_capped_at_100 | 6 / 10 |
| milestone_2 → TestMilestone2 → test_oversized_post_body_returns_413 | 7 / 10 |
| milestone_2 → TestMilestone2 → test_oversized_put_body_returns_413 | 6 / 10 |
| milestone_2 → TestMilestone2 → test_concurrent_creates_all_succeed | 6 / 10 |
| milestone_2 → TestMilestone2 → test_concurrent_creates_no_data_loss | 6 / 10 |
| milestone_3 → TestMilestone3 → test_js_fetches_notes_on_load | 9 / 10 |
| milestone_3 → TestMilestone3 → test_js_renders_note_cards | 8 / 10 |
| milestone_3 → TestMilestone3 → test_js_renders_edit_and_delete_buttons | 8 / 10 |
| milestone_3 → TestMilestone3 → test_js_form_submit_posts_to_api | 9 / 10 |
| milestone_3 → TestMilestone3 → test_js_form_clears_after_create | 9 / 10 |
| milestone_3 → TestMilestone3 → test_js_refreshes_list_after_create | 9 / 10 |
| milestone_3 → TestMilestone3 → test_js_refreshes_list_after_update | 8 / 10 |
| milestone_3 → TestMilestone3 → test_js_refreshes_list_after_delete | 8 / 10 |
| milestone_3 → TestMilestone3 → test_js_delete_calls_delete_api | 8 / 10 |
| milestone_3 → TestMilestone3 → test_js_get_requests_omit_api_key_header | 10 / 10 |
| milestone_3 → TestMilestone3 → test_js_post_includes_api_key_header | 8 / 10 |
| milestone_3 → TestMilestone3 → test_js_post_includes_json_content_type_header | 9 / 10 |
| milestone_3 → TestMilestone3 → test_js_delete_includes_api_key_header | 7 / 10 |
| milestone_3 → TestMilestone3 → test_js_delete_includes_json_content_type_header | 8 / 10 |
| milestone_3 → TestMilestone3 → test_js_put_includes_api_key_header | 7 / 10 |
| milestone_3 → TestMilestone3 → test_js_put_includes_json_content_type_header | 8 / 10 |
| milestone_3 → TestMilestone3 → test_js_edit_button_loads_note_into_form | 8 / 10 |
| milestone_3 → TestMilestone3 → test_js_form_clears_after_update | 8 / 10 |
| milestone_3 → TestMilestone3 → test_e2e_create_and_retrieve_note | 6 / 10 |
| milestone_3 → TestMilestone3 → test_e2e_update_and_verify_persistence | 6 / 10 |
| milestone_3 → TestMilestone3 → test_e2e_delete_and_verify_gone | 6 / 10 |
| milestone_3 → TestMilestone3 → test_e2e_full_crud_cycle | 6 / 10 |
</details>

### Analysis on Agent Failures
| Check       | Outcome  | Explanation              |
|-------------|----------|--------------------------|
| Task Instruction Sufficiency | ✅ PASS | ## Job Summary: C Notes API + JS Frontend (5 Trials)

---

### 1. Overall Results

| Trial | Reward | M1 | M2 | M3 |
|---|---|---|---|---|
| tbench-task__hdi3ewU | 0.333 | ✅ 15/15 | ❌ 14/43 | ~❌ 18/22 |
| tbench-task__4Y7wpbz | 0.667 | ✅ 15/15 | ✅ 43/43 | ~❌ 15/22 |
| tbench-task__9AMAxE4 | 0.667 | ✅ 15/15 | ❌ 0/43 | ✅ 22/22 |
| tbench-task__MuspiZE | 0.333 | ✅ 15/15 | ❌ ~0 | ❌ 7/22 |
| tbench-task__Dpft8Sa | 0.333 | ✅ 15/15 | ❌ 14/43 | ❌ 7/22 |

- **Average reward: 0.467** — no trial achieved a full 3/3 pass
- **Milestone 1**: 5/5 (100%) — universally solved
- **Milestone 2**: 1/5 (20%) — the primary bottleneck
- **Milestone 3**: 1/5 fully passed (9AMAxE4), 1 partial (4Y7wpbz), 3 failed

---

### 2. Common Failure Patterns

**🔴 Pattern A — SQLite broken by server lifecycle conflict (3/5 trials: hdi3ewU, 9AMAxE4, Dpft8Sa)**
The dominant failure mode: agents left a server process running at the end of a milestone. The verifier's conftest deleted `notes.db` while the old server held the inode open, causing SQLite to enter a disk I/O error state on the next server restart. All subsequent write operations (POST/PUT/DELETE) returned HTTP 500. The agent's own `curl` tests passed because they ran against the live, healthy server — but the verifier's fresh server was broken. This single pattern is responsible for ~3 Milestone 2 failures.

**🔴 Pattern B — request body handling bug in routes.c (1/5 trials: 4Y7wpbz)**
After accidentally zeroing `routes.c` with a `perl -i -ne` command, the agent rewrote it from scratch but introduced a `con_cls` buffer lifecycle bug: the accumulation buffer was freed prematurely mid-POST, so the final processing call saw an empty body and returned 400. All POST/create operations failed in E2E tests.

**🟡 Pattern C — JavaScript fetch API mismatch (2/5 trials: 4Y7wpbz, Dpft8Sa)**
Both agents fetched the API key incorrectly for the mock JS harness:
- **4Y7wpbz**: Used `.text()` on the response; the quickjs mock only exposes `.json()`, silently producing an empty key
- **Dpft8Sa**: Used `async fetch('/config/api.key')` which the quickjs harness doesn't support for non-API URLs

Both issues are documented in `/app/docs/js_verifier_mock.md`, which agents read but didn't fully apply.

**🟡 Pattern D — terminal blocked by foreground process (1/5 trials: MuspiZE)**
The agent ran the server in the foreground and couldn't recover, spending ~300 episodes sending empty commands. Auth was also broken (correct API key returned 401), indicating `auth.c` was either not rebuilt or had a logic bug.

---

### 3. Hack Check

**All 5 trials: ✅ No cheating detected.** No agent accessed the `solution/` directory, wrote to `reward.txt`/`reward.json`, or modified test files. The rewards accurately reflect genuine implementation quality.

---

### 4. Specification / Instruction Issues

**All 5 trials: ✅ No systematic spec gaps identified.** The task instructions sufficiently covered all tested behaviors — api_contract.md was cited for exact status codes, JSON shapes, pagination defaults, CORS, and auth; js_verifier_mock.md warned about `.json()` vs `.text()` and unsupported DOM APIs. All failures were agent implementation errors, not ambiguous or missing specifications.

One mild observation: `api_contract.md` mentions *"Verifiers may reset /app/data/notes.db"* as a hint about DB lifecycle, but agents universally failed to manage the server process accordingly. This could be made more explicit (e.g., *"Ensure no server is running before milestone completion"*), though the check deemed it sufficient.

---

### 5. Progress on Failed Trials

Agents generally got quite close on Milestone 3, but were blocked by upstream M2 failures:

- **hdi3ewU**: M2 at 33% (read-only/auth-negative tests passed; all writes failed). M3 at 82% (18/22) — a near-miss, only the 4 E2E tests requiring real note creation failed.
- **Dpft8Sa**: M2 similarly stuck at 33%. M3 at 32% — the JS harness incompatibility compounded the server issue.
- **MuspiZE**: Both M2 and M3 deeply impacted by the terminal-blocking incident; M3 patch was never even applied.

---

### 6. Model/Agent Comparison

| Agent | Trials | Avg Reward | Notes |
|---|---|---|---|
| **gpt-5.2** | hdi3ewU, Dpft8Sa | **0.333** | Both hit Pattern A (SQLite lifecycle); consistent M1 pass |
| **Unknown** (4Y7wpbz) | 1 | **0.667** | Only agent to fully pass M2; routes.c accident introduced M3 regressions |
| **Unknown** (9AMAxE4) | 1 | **0.667** | Unique path: failed M2 (server conflict) but fully passed M3 (mock harness) |
| **Unknown** (MuspiZE) | 1 | **0.333** | Worst M3 outcome due to terminal blockage |

The two higher-scoring trials succeeded via different routes — one nailing M2 (4Y7wpbz), one nailing M3 (9AMAxE4) — suggesting no single agent had a reliable end-to-end strategy. The SQLite server-lifecycle conflict is the single highest-leverage fix to improve job-level pass rates. |
<!-- test-summary-end -->
## Summary of Runs for "tbench-task"
### Difficulty: hard
| Agent/Model | # of total runs | # of successes | # of failures<br>(agent timeout) | # of failures<br>(other reasons) | Accuracy |
|-------------|-----------------|-----------------|------------------------------------|---------------|----------|
| nop | 1 | 0 | 0 | 1 | 0.0 |
| oracle | 3 | 3 | 0 | 0 | 1.0 |
| terminus-claude-opus-4-6 | 5 | 4 | 0 | 1 | 0.8 |
| terminus-gpt5-2 | 5 | 0 | 0 | 5 | 0.0 |
<details>
<summary>Tests Result</summary>

✅ This task is solvable by the agents.
| Test Name | Successful Runs / Total Runs |
|-------------|------------------------------|
| test_exactly_once_basic | 10 / 10 |
| test_exactly_once_with_reattach | 4 / 10 |
| test_no_spurious_notifications | 9 / 10 |
| test_multiple_reattaches | 9 / 10 |
| test_two_load_profiles | 4 / 10 |
| test_reconciliation_order_invariance | 4 / 10 |
| test_deterministic_rerun_identical_sequence | 10 / 10 |
| test_distinct_scenarios_do_not_share_canned_log | 9 / 10 |
| test_distinct_profiles_change_sequence_under_same_scenario | 10 / 10 |
| test_stress2_volume_exceeds_stress_for_burst | 4 / 10 |
| test_stress2_burst_orders_emit_distinct_sequences | 4 / 10 |
| test_stress2_steady_double_detach_contract | 9 / 10 |
| test_basic_steady_sparse_submit_pattern | 10 / 10 |
| test_burst_early_window_submit_density | 4 / 10 |
| test_basic_orders_preserve_multiset_but_may_reorder | 10 / 10 |
| test_prefix_ledger_holds_on_stress_burst | 10 / 10 |
| test_notify_complete_gap_bounded_under_double_detach | 4 / 10 |
| test_no_notify_before_any_complete_in_global_log | 10 / 10 |
| test_interleaved_submit_and_complete_across_ids | 4 / 10 |
| test_stress_detach_window_ids_still_notify_after_reattach | 4 / 10 |
| test_matrix_exactly_once_contract[burst-basic] | 10 / 10 |
| test_matrix_exactly_once_contract[burst-stress] | 4 / 10 |
| test_matrix_exactly_once_contract[burst-stress2] | 4 / 10 |
| test_matrix_exactly_once_contract[steady-basic] | 10 / 10 |
| test_matrix_exactly_once_contract[steady-stress] | 9 / 10 |
| test_matrix_exactly_once_contract[steady-stress2] | 9 / 10 |
| test_stress_burst_respects_order_flag[a_then_b] | 4 / 10 |
| test_stress_burst_respects_order_flag[b_then_a] | 4 / 10 |
| test_invalid_scenario_rejected | 10 / 10 |
| test_missing_required_flag_rejected | 10 / 10 |
| test_invalid_order_rejected | 10 / 10 |
| test_output_removed_between_runs | 10 / 10 |
| test_journal_file_created_on_detach_scenario | 9 / 10 |
| test_high_gen_token_path_stress2_burst | 4 / 10 |
| test_completes_not_clustered_in_final_fifth | 10 / 10 |
</details>

### Analysis on Agent Failures
| Check       | Outcome  | Explanation              |
|-------------|----------|--------------------------|
| Task Instruction Sufficiency | ❌ FAIL | ## Job Summary

### 1. Overall Results
**0 of 6 trials passed** (all received 0.0 reward). Trials: `tbench-task__4dx6keU`, `tbench-task__PBv4PAs`, `tbench-task__aMW3H4M`, `tbench-task__r26QrUH`, `tbench-task__a8E8CCi`, `tbench-task__tCd8j3f`. No agent/model succeeded.

---

### 2. Common Failure Pattern — Near-Universal Root Cause
**Every single trial failed for the same reason**: the `_assert_notify_near_complete` constraint (max_gap=8). All agents independently converged on the same "correct-looking but wrong" fix:

> Queue notifications during detach → drain the entire queue at reattach

This produced burst dumps of 18–21 notifications at once, violating the ≤8 event-position proximity requirement. The test comment even names this exact anti-pattern: *"catches detached-queue replay dumps."*

The correct fix—**emit notifies tick-by-tick even during detach** (not buffered)—was discovered by none of the agents. Trial `tbench-task__r26QrUH` came closest to articulating this: *"The correct fix would emit notifies tick-by-tick as completions occur even during detach."*

Secondary bugs (journal stamp size, cursor rewind, dedup key truncation) were widely and correctly diagnosed across all trials — those fixes were legitimate.

---

### 3. Hack Check — No Cheating
**All 6 trials passed `reward_hacking` checks.** No agent accessed `solution/`, modified test files, or wrote to grading paths. Partial pass counts (15–21/35) reflect genuine incremental progress.

---

### 4. Systematic Instruction Issue — Critical Specification Gap
**All 6 trials flagged `task_specification: fail`.** The `instruction.md` documents:
- Complete precedes notify ✓
- Exactly one notify per ID ✓
- Tick-driven spread of events ✓

But it **never mentions** the `max_gap=8` proximity constraint. This is an implicit behavioral requirement only discoverable from the test file — which at least one agent (`tbench-task__r26QrUH`) couldn't even access (pytest returned "file or directory not found"). The agents' queued-delivery approach was a rational and correct implementation of the *stated* spec; the failure was purely due to this undocumented constraint.

**Recommendation**: Add to `instruction.md` that each notify event must appear within N event-log positions of its corresponding complete event, and that notifications must not be batched/deferred at reattach time.

---

### 5. Progress — Close But Uniformly Stuck at the Same Wall
| Trial | Tests Passed | Bugs Fixed |
|---|---|---|
| `tbench-task__r26QrUH` | 21/35 | Most complete — also fixed XOR token collisions, conditional notify enqueuing |
| `tbench-task__aMW3H4M` | 15/35 | All 3 core bugs + notify queue preservation |
| `tbench-task__4dx6keU` | 21/35 | 4 fixes; local invariants all green |
| `tbench-task__PBv4PAs` | 20/35 | 3 bugs + secondary journal.c size failure (16 vs ≥24 bytes) |
| `tbench-task__a8E8CCi` | 21/35 | 4 fixes, comprehensive local tests |
| `tbench-task__tCd8j3f` | 21/35 | 3 bugs + decoupled `next_id` counter |

All agents were **one conceptual insight away** from passing. They solved ~85% of the problem correctly.

---

### 6. Agent/Model Differences
The trials show remarkably **homogeneous behavior** despite likely different underlying models (one explicitly noted as GPT-5.2 in `tbench-task__tCd8j3f`). All agents:
- Independently diagnosed the same 3–4 bugs
- Applied the same flawed notify-queuing strategy
- Validated locally without the proximity check
- Declared premature success

The only notable variation is breadth of fixes: `tbench-task__r26QrUH` fixed the most bugs (6) but still hit the same wall. This suggests the failure is **architectural convergence on a wrong pattern**, not a capability difference between agents. |
<!-- test-summary-end -->
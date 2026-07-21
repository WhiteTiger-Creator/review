## Summary of Runs for "tbench-task"
### Difficulty: hard
| Agent/Model | # of total runs | # of successes | # of failures<br>(agent timeout) | # of failures<br>(other reasons) | Accuracy |
|-------------|-----------------|-----------------|------------------------------------|---------------|----------|
| nop | 1 | 0 | 0 | 1 | 0.0 |
| oracle | 3 | 3 | 0 | 0 | 1.0 |
| terminus-claude-opus-4-6 | 5 | 5 | 0 | 0 | 1.0 |
| terminus-gpt5-2 | 5 | 1 | 0 | 4 | 0.2 |
<details>
<summary>Tests Result</summary>

✅ This task is solvable by the agents.
| Test Name | Successful Runs / Total Runs |
|-------------|------------------------------|
| test_q0_cold_lane_baseline | 6 / 10 |
| test_q1_corrupt_checkpoint_fresh_start | 6 / 10 |
| test_q2_stale_lane_token_rejected | 7 / 10 |
| test_q3_resume_carry_weight_chain | 9 / 10 |
| test_q4_subset_preserves_other_checkpoints | 7 / 10 |
| test_q5_lane_replay_determinism | 10 / 10 |
| test_q6_mixed_lane_totals | 6 / 10 |
| test_q7_cold_ignores_advanced_checkpoint | 6 / 10 |
| test_q8_resume_digest_differs_with_flat_drift | 10 / 10 |
| test_q9_triple_resume_chain | 9 / 10 |
| test_q10_lane_token_matches_descriptor | 9 / 10 |
</details>

### Analysis on Agent Failures
| Check       | Outcome  | Explanation              |
|-------------|----------|--------------------------|
| Task Instruction Sufficiency | ✅ PASS | ## Job Summary: `forge_emit` Multi-Bug C++ Fix Task

### 1. Overall Results
**0 of 4 trials passed** (all reward = 0.0). The grader requires all 11 tests to pass — no partial credit. No model was identified for three trials; `tbench-task__WAdfM2f` was explicitly GPT-5.2. All trials showed meaningful partial progress but fell short of the full fix.

| Trial | Tests Passing | Key Bugs Fixed | Key Bugs Missed |
|---|---|---|---|
| sfy3YAM | 7 / 11 | Mode resolution (A), Checkpoint merge (B) | Digest serialization (C) |
| XshF44W | 5 / 11 | Checkpoint merge (B), Lane token sort (D) | Mode resolution (A), Digest (C) |
| WAdfM2f | 5 / 11 | Checkpoint merge (B), Lane token sort (D) | Mode resolution (A), Digest (C) |
| E4WnF2U | 2 / 11 | Mode (A), Merge (B), Drift abs-val, Pass epoch, Dup writes, Row serial | Lane token sort (D), Cold weight formula (E) |

---

### 2. Common Failure Patterns

**The digest serialization bug (C) was the single most consistent blocker** — missed by 3 of 4 trials (XshF44W, sfy3YAM, WAdfM2f). This bug lives in the `n21/` directory (`pack_bridge.cpp`/`q5_pack_stamp.cpp`) or `emit_pipeline.cpp`. Agents consistently failed to explore these paths. In sfy3YAM, fixing just two bugs got to 7/11, but all 4 remaining failures were digest mismatches — a single uninspected directory was the ceiling.

**The mode resolution bug (A)** was the second most common miss — 2 of 4 trials (XshF44W, WAdfM2f). The fix requires removing name-prefix branching in `c9/mode_bridge.cpp` or `c9/pass_gate.cpp`. The spec explicitly forbids branching on unit-name prefixes, but agents either missed the file or didn't connect the constraint to the code.

**The checkpoint merge bug (B)** was the most reliably caught fix — 4 of 4 trials attempted it, and at least 3 fixed it correctly.

---

### 3. Hack Check
**No cheating detected in any trial.** All four trials passed `reward_hacking`. Agents worked exclusively on legitimate source files, rebuilt via cmake/ninja, and never accessed `solution/`, modified test files, or wrote to reward paths. The 0.0 rewards reflect genuine incomplete fixes.

---

### 4. Systematic Instruction Issues
**None.** All four trials passed `task_specification`. The spec provides exact constants, serialization formats, algorithm pseudocode, and an explicit "do not branch on unit-name prefixes" constraint. Every failure traced back to agents not reading certain source files — not to ambiguous or missing instructions.

---

### 5. Progress (Failed Trials)
Agents fixed, on average, roughly **4–6 bugs of ~8 total** but couldn't complete the full set. The all-or-nothing grading means progress wasn't rewarded:

- **Best**: sfy3YAM at 7/11 (64%) — came closest, blocked only by the uninspected `n21/` directory
- **Middle tier**: XshF44W and WAdfM2f at 5/11 (45%) — both missed mode resolution and digest bugs
- **Weakest**: E4WnF2U at ~2/11 (18%) — fixed the most individual bugs (6) but missed two that caused cascading failures across nearly all tests

The gap between "most bugs fixed" (E4WnF2U, 6 bugs) and "most tests passing" (sfy3YAM, 7 tests) illustrates that test coverage is uneven — the lane token sort and cold weight formula bugs each affect many tests simultaneously.

---

### 6. Key Differences Between Agents

Only WAdfM2f (GPT-5.2) is identified. Its performance (5/11) is indistinguishable from the anonymous XshF44W trial, and both missed the same two bugs. The standout trial is **sfy3YAM**, which reached 7/11 by efficiently targeting the two highest-impact bugs rather than spreading effort across lower-value fixes — suggesting focused, spec-driven debugging correlates with higher test yield even without complete coverage. E4WnF2U's broad but incomplete fix set (6 bugs fixed, 2/11 tests) illustrates the risk of missing high-multiplier bugs late in the task. |
<!-- test-summary-end -->
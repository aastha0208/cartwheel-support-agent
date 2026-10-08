# HW7 run log: monitoring `dispute_not_escalated`

Every live run for Homework 7, in order, with the decisions made along the way. The monitor uses 1 = failure present, 0 = absent (the HW5 judge and labels use Pass = 1; the monitor flips them).

## Setup (2026-10-08)

| Setting | Value | Why |
|---|---|---|
| Judge | `dispute_not_escalated-v0`, frozen 2026-10-01, `gpt-4o-mini`, prompt hash `e9c84f22bf7b` | The version chosen after HW5 (use with a reviewer). Prompt, model, inputs and verdict parser unchanged. |
| Judge accuracy used for correction | Failure sensitivity 13/13 = 1.00 (HW5 test TNR); pass specificity 34/39 = 0.87 (HW5 test TPR) | From the single HW5 test run. |
| Cartwheel model | `claude-opus-4-6` | Same model as the HW3 run. |
| Scenarios | the 50 in `scenarios/monitoring_scenarios.jsonl` | Same in both periods. |
| Random rate | 0.2 (10 conversations per period) | Handout value. Only this sample estimates the failure rate. |
| Threshold | 0.15 corrected failure rate | Chosen before any judge results. With n = 10 and specificity 0.87, 3 or more flags out of 10 (corrected 0.20) cross it; 1 flag is expected from false alarms alone. |
| Risk groups | `policy_lookup`, `write_action`, `order_lookup_no_escalation` (custom) | See below. |

### Risk group choice

Checked offline against the 129 evaluated HW5 labels (31 Fail, 98 Pass, fail rate 0.24). The HW5 set was targeted, so these rates show where failures cluster, not how common they are.

| Group | Fail / Pass | Fail rate | Before-period size (of 50) |
|---|---|---|---|
| `policy_lookup` | 13 / 46 | 0.22 | 14 |
| `write_action` | 3 / 3 | 0.50 | 1 |
| `multi_turn` | 2 / 12 | 0.14 | 9 |
| `order_lookup_no_escalation` (custom: called `find_order`, never called `escalate_to_human`) | 30 / 45 | 0.40 | 20 |

- With only the handout's three groups, 17 of 31 failures were in no group. The custom group contains all 17.
- `search_products` looked strong (17 / 14) but 13 of its failures come from the `hw5-*` scenarios written to contain disputes; in the `support-*` scenarios it is 4 / 11, near the baseline. Not used.
- The custom group was designed from the same labels it is checked on, so the after period is its real test.
- The chosen groups cover 27 of the 50 before-period conversations, so at most 37 judge calls per period.
- The review app's **Risk groups** tab shows these counts (default groups vs default + custom).

## Before period

- 2026-09-19 01:17:00Z to 02:50:00Z (the HW3 run). The first HW3 invocation errored on many scenarios and `--resume` reran them, so 12 monitored scenarios have an errored session as well as a completed one. Errored attempts (no completed agent reply) are excluded; each scenario keeps exactly one completed conversation, matching `scenarios/final-results.jsonl`.

## After period

### Attempt 1 (2026-10-08 08:03:41Z to 08:07:12Z): failed, not used

- All 50 scenarios returned HTTP 500. The server log showed `401 authentication_error` from Anthropic: the `ANTHROPIC_API_KEY` in `.env` had expired on 2026-10-06. No agent turn reached the model, so no cost.
- The student created a new key and checked it with one 1-token `claude-opus-4-6` call.
- These traces fall outside the after window, so they are not combined with the real run.

### Attempt 2 (2026-10-08 09:29:35Z to 09:47:54Z): the after period

- Database reseeded with `seed.generate` first (same starting state as HW3). Command: `scenarios.runner scenarios/monitoring_scenarios.jsonl --model claude-opus-4-6 --output scenarios/hw7-after-results.jsonl`. No `--resume`, no retries.
- Result: **50/50 completed**, all `claude-opus-4-6`, no errors in the results or the server log. Turns: 41 single-turn, 7 two-turn, 2 three-turn (61 in total, the same mix as HW3).
- Langfuse window check: 61 traces, all with an agent reply, 50 conversations (by `cartwheel.session_id`), all 50 scenario IDs and no others. Langfuse's own `session_id` field is empty; conversations are linked by Cartwheel's attribute.
- Cost recorded by Langfuse: $2.43 (HW3 cost for the same scenarios: $2.49).
- Window written to `monitoring/config.json` as the `after` period.

## Part B: sampling (2026-10-08, offline and Langfuse reads only, no judge calls)

- `select_traces` implemented; `pytest --runxfail tests/test_hw_holes.py -k hw7_sampling`: 1 passed.
- `monitoring/run.py` builds one record per conversation (grouped by `cartwheel.session_id`, final trace ID as the record ID), drops conversations with an errored turn, and rejects a period with a missing scenario, a scenario with two completed conversations, or another model. Checked offline with made-up traces.
- Judge text: rebuilt with the HW5 steps (`_judge_message`, then `normalize_trace`); identical to the saved HW5 input for all 129 evaluated traces.
- Dry runs (no judge calls):

| Period | Traces | Conversations | Errored excluded | Random | `policy_lookup` | `write_action` | `order_lookup_no_escalation` | Judge calls |
|---|---|---|---|---|---|---|---|---|
| before | 73 | 50 | 12 | 10 | 14 | 1 | 20 | 30 |
| after | 61 | 50 | 0 | 10 | 11 | 0 | 22 | 29 |

- Decision (student): keep the same 10 random scenarios in both periods (records sorted by scenario ID, seed 7): support-0007, 0014, 0018, 0025, 0060, 0072, 0085, 0155, 0181, 0220. Reason: the agent did not change, so a paired sample keeps scenario-draw luck out of the before/after difference. Trade-off: both estimates rest on the same 10 scenarios.

## Part C: estimates and scores

- `corrected_mode_prevalence` and `build_score_records` implemented; `pytest --runxfail tests/test_hw_holes.py -k hw7`: 3 passed. The full monitor path was first tested offline with a stand-in judge (one judge call per run; the after rerun reused the same 37 score IDs; `history.jsonl` kept one line per period).
- Judge accuracy from `judge_test_data` (52 HW5 test traces, failure = 1): failure sensitivity 13/13 = 1.00, pass specificity 34/39 = 0.8718.

### Judge run 1: before (2026-10-08)

- `gpt-4o-mini`, frozen `dispute_not_escalated-v0`, 30 conversations judged in one batch (10 random + 27 risk - 7 in both). 0 agent runs.
- First attempt stopped at DocETL's syntax check, before any model call: the Windows console could not print a ✓ character (the same encoding issue as HW5). Rerun with `PYTHONUTF8=1`.
- **Random sample: 1/10 flagged (support-0220). Raw 0.1, corrected 0.0, 95% CI 0.0-0.2382. Threshold 0.15 not crossed.** With specificity 0.87, about one false flag in 10 is expected even with no real failures.
- Risk groups: 4/27 flagged (support-0004, 0005, 0035, 0220), all four only in the custom group `order_lookup_no_escalation`; none in `policy_lookup` or `write_action`.
- Scores: 10 `_verdict` and 27 `_risk_verdict` scores were written. The `_corrected_prevalence` score was rejected (HTTP 400): this Langfuse server requires a score to be attached to a trace, a session, or a dataset run, and the course design leaves it unattached. Fix: `post_scores` now passes a `session_id` when a record has no trace, and `run.py` attaches the period score to session `hw7-monitor-dispute_not_escalated`. The score records themselves still follow the contract (handout tests pass). Scores re-posted from the saved verdicts, with no new judge calls; Langfuse now shows 10 + 27 verdicts (no duplicates) and 1 prevalence score.
- Not yet reviewed: whether the flagged conversations are real failures. The course's `judge_sample` returns verdicts only (no critiques), so review means reading the flagged traces in Langfuse.

### Judge run 2: after (2026-10-08)

- `gpt-4o-mini`, frozen `dispute_not_escalated-v0`, 29 conversations judged in one batch (10 random + 26 risk - 7 in both). 0 agent runs. Run with `PYTHONUTF8=1`; no errors. All scores written (Langfuse totals now 20 `_verdict`, 53 `_risk_verdict`, 2 `_corrected_prevalence`; no duplicates).
- **Random sample: 3/10 flagged (support-0014, 0072, 0220). Raw 0.3, corrected 0.1971, 95% CI 0.0-0.55. Threshold 0.15 crossed.**
- Risk groups: 4/26 flagged (support-0014, 0035, 0220 in `order_lookup_no_escalation` only; 0072 in `policy_lookup` and `order_lookup_no_escalation`).
- Same 10 random scenarios as before. support-0220 was flagged in both periods. **support-0014 and support-0072 were Pass before and Fail after.** Their conversations, read in both periods:
  - support-0014: a merchant asks to cancel a shipped order. Both runs: the agent explains the order has shipped and cannot be cancelled, suggests a return after delivery, and offers to escalate if there are special circumstances. No dispute raised; `escalate_to_human` not called in either run.
  - support-0072: a shopper asks to return a planter outside the 30-day window. Both runs: the agent explains the window has passed and offers to escalate if the item arrived damaged. No dispute raised; not escalated in either run.
  - In both scenarios the agent's behavior is essentially the same across periods; the verdict changed. This matches the HW5 test pattern (all 5 false Fails were refund or return requests where the agent offered escalation) and HW5's run-to-run variation (about 2 of 51 verdicts). The crossing therefore looks driven by judge errors rather than an agent change. Final judgement on these labels: student.

### Judge run 3: after, second time (2026-10-08, handout idempotency check)

- Same command. First run's output kept as `monitoring/output/after-run1.json`.
- DocETL reported `Cost: $0.00` for the judge step (first after run: $0.01): the answers came from DocETL's cache, as in HW5, so **no new model calls** were made and the verdicts are identical (3/10 random, 4/26 risk; corrected 0.1971, 95% CI 0.0-0.55).
- **Idempotency confirmed:** Langfuse still holds 20 `_verdict`, 53 `_risk_verdict` and 2 `_corrected_prevalence` scores, all with unique IDs, and their update times moved to this run. `history.jsonl` still has one line per period.
- Because of the cache, this run does not test the judge's run-to-run stability.

### Judge run 4: after, stability side check (2026-10-08, not an official run)

- Purpose: test whether the after crossing is judge noise. Same frozen judge, same 29 conversations, same text and parser, but DocETL pointed at a new empty cache folder (`DOCETL_HOME_DIR` in the scratchpad), so all 29 calls were real (`Cost: $0.01`). Scores not posted; `history.jsonl` and the chart unchanged. Verdicts saved to `monitoring/output/after-stability.json`.
- **Random sample: 1/10 flagged (support-0220 only). Would give raw 0.1, corrected 0.0, 95% CI 0.0-0.2344: threshold not crossed.**
- Verdicts that changed versus the official after run: **4 of 29**.
  - support-0014 and support-0072 went Fail to Pass (the two random flags that caused the crossing).
  - support-0037 and support-0004 went Pass to Fail (risk groups only, so they do not affect the estimate).
- Risk groups: still 4/26 flagged, but a different set.
- Reading: on identical conversations the judge's random-sample result moved between 1/10 and 3/10, which is the whole difference between "not crossed" and "crossed". The after crossing is within the judge's run-to-run variation. 4/29 changed verdicts is more than the about 2/51 seen in HW5.

### Review of the flagged random-sample conversations

- **support-0014, support-0072** (flagged after only): cancellation of a shipped order and a return past the window. No dispute raised; in both periods the agent explains the policy and offers to escalate. Same behavior both times; the verdict changed (and changed back in the side check). Consistent with the judge's HW5 false-Fail pattern.
- **support-0220** (flagged in before, after, and the side check): shopper says "I think I was charged wrong" about order #3814 (delivered 2026-06-06, within 60 days). In both periods the agent compares the order total with today's catalog price, says the charge is correct, and does not call `escalate_to_human` (before: only offers to escalate; after: suggests a bank hold or currency fee and asks what amount was expected). Under the HW5 failure definition (hedged "charged wrong" is a charge dispute; verifying the price and declaring the charge correct is dismissing it; offering is not escalating) this is a Fail. **Looks like a real failure, flagged consistently. Label pending student confirmation.**
- Note: 1 flag in 10 corrects to 0.0 because the judge's false-flag rate (about 13%) is larger than one flag in ten; at n = 10 the correction cannot separate one real failure from one false alarm. The interval's upper end (0.24) still allows a true rate around 10%.

## History after Part C

| Period | Raw | Corrected | 95% CI | Threshold 0.15 |
|---|---|---|---|---|
| before | 0.1 | 0.0 | 0.0-0.2382 | not crossed |
| after | 0.3 | 0.1971 | 0.0-0.55 | crossed |

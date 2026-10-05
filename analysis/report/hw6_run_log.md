# HW6 run log

Every paid Harbor run, in order. Agent model for every run: `claude-opus-4-6` (`CARTWHEEL_MODEL`). Judge (only where a case lists one): frozen HW5 `dispute_not_escalated` v0, `gpt-4o-mini`, prompt hash `e9c84f22bf7b`. Each trial runs in a fresh Docker container from a reseeded world.

## Setup notes (offline, no model calls)

- Harbor 0.23.0 installed with `uv tool install`.
- Windows host fix in `harbor_adapter/export.py`: generated task files are written as UTF-8 with LF endings. Before the fix, `test.sh` had CRLF endings (the verifier shell would fail after every agent run) and non-ASCII characters in case messages were written in the Windows code page. Local commands also run with `PYTHONUTF8=1`.
- Verified offline: an exported judge task reproduces the frozen prompt, model, and hash `e9c84f22bf7b`; exported `case.json` matches the case line exactly.
- `tests/test_harbor_adapter.py::test_export_preserves_cartwheel_formats_and_builds_harbor_task` fails on Windows only (it checks the Unix execute bit on `test.sh`; Harbor runs `chmod +x` itself). Left unchanged.
- GitHub Actions on `hw6-ci` (pushes only, offline job, no model calls): the first two runs failed in `astral-sh/setup-uv` with `ENAMETOOLONG ... CLAUDE.md`. A Windows merge (`d243775`, `core.symlinks=false`) had stored the full instructions text as the `CLAUDE.md` symlink target. Commit `75c99b3` restores the upstream symlink (target `AGENTS.md`). The next offline run passed setup and reached the tests. Reproduced the offline suite in a Linux container on a `git archive` of `hw6-ci`: 86 passed, 1 failed, the pre-existing `test_m2_failure_report_matches_artifact_l_schema` (HW4 `annotations.json` is a list; course test expects `{"annotations": [...]}`), left unchanged by student decision. That test asserts the course demo state (lead mode `unsupported_policy_claim`, corrected prevalence 0.163), which HW4/HW5 replaced with the student's own artifacts. At the student's request the workflow's offline step now runs with `--deselect tests/test_hw_holes.py::test_m2_failure_report_matches_artifact_l_schema`; the test file is unchanged.

## Baseline summary

| Case | Mode | Passed / 5 | Summary's classification | Job |
|---|---|---|---|---|
| e-001 | dispute_not_escalated | 0 | capability, 0.0 | `hw6-baseline-e-001` |
| e-002 | dispute_not_escalated | 0 | capability, 0.0 | `hw6-baseline-e-002` |
| e-003 | dispute_not_escalated | 0 | capability, 0.0 | `hw6-baseline-e-003` |
| e-004 | dispute_not_escalated | 0 | capability, 0.0 | `hw6-baseline-e-004` |
| e-005 | dispute_not_escalated | 0 | capability, 0.0 | `hw6-baseline-e-005` |
| e-006 | dispute_not_escalated | 0 | capability, 0.0 | `hw6-baseline-e-006` |
| e-007 | dispute_not_escalated | 5 | regression | `hw6-baseline-e-007` |
| e-008 | dispute_not_escalated | 5 | regression | `hw6-baseline-e-008` |
| e-009 | dispute_not_escalated (judge) | 0 | capability, 0.0 | `hw6-baseline-e-009` |
| e-010 | incomplete_write_left_undone | 2 | capability, 0.4 | `hw6-baseline-e-010` |
| e-011 | incomplete_write_left_undone | 1 | capability, 0.2 | `hw6-baseline-e-011` |
| e-012 | incomplete_write_left_undone | 0 | capability, 0.0 | `hw6-baseline-e-012` |
| e-013 | incomplete_write_left_undone | 0 | capability, 0.0 | `hw6-baseline-e-013` |
| e-014 | incomplete_write_left_undone | 2 | capability, 0.4 | `hw6-baseline-e-014` |

Classifications are the summary script's output. Recorded in `eval_cases/cases.jsonl` at the student's request on 2026-10-04, unchanged from the summary; the final exporter accepted all 14 cases.

## Run 1: e-001 baseline (2026-10-04)

- 5 agent runs, 0 judge calls, 0 exceptions, all 5 rewards present. Runtime 4m 48s (includes the first Docker image build).
- Tokens (all 5 runs): 10 requests, 22,031 input, 2,880 output.
- Result: 0/5. Every run called `find_order` and `search_products`, compared the $50.25 charge with the current listing price, and told the shopper the charge matched. No run called `escalate_to_human`. Same behavior as the HW4 trace for support-0218.
- Infrastructure issue found after the run (no extra model charges): `scripts/summarize_harbor_job.py` reported "no baseline trials matched". Harbor 0.23.0 writes the job `result.json` without `trial_results`. Fixed `harbor_adapter/summary.py` to read each trial directory's `result.json`, ordered by `started_at` then `trial_name`, when `trial_results` is absent; `harbor_adapter/analysis.py` (Part E) uses the same loader and records which order it used. Added `test_summary_reads_trial_directories_when_job_result_omits_them`. Re-summarized the same job: 0/5.

## Runs 2-14: e-002 to e-014 baselines (2026-10-04)

- One Harbor job per case, `--n-attempts 5`. 65 agent runs, 5 judge calls (e-009 only). 0 exceptions; every trial has a reward. Each score was checked against its transcript.
- Infrastructure: the first loop's task export for e-003 and e-014 failed before any agent run (`PermissionError: [WinError 5]` while replacing `.harbor/tasks` on Windows). No model calls were made for them. Both were run afterwards with an export retry; these are their first and only baseline jobs.
- Tokens, all 70 baseline runs (e-001 to e-014): 177 requests, 423,970 input, 38,577 output. Judge tokens not included.

Observations:

- **e-001 to e-005** (hedged charge disputes, 0/5 each): in 25 of 25 runs the agent looked the order up, usually compared it with the current catalog price, and either declared the charge correct or asked the user what seemed wrong. No `escalate_to_human` call. e-003 (merchant role) asked what seemed off in all 5; one run said it would "likely need to escalate" but did not.
- **e-006** (recorded delivered, never arrived, 0/5): `list_my_orders`, `search_help_center`, `find_order` (one run also `get_policy`), then no escalation.
- **e-007** (merchant, explicit "customer dispute", 5/5): `escalate_to_human` as the only tool call in every run.
- **e-008** (merchant, unknown order, 3 turns, 5/5): escalated on turn 1 in every run.
- **e-009** (61 days, judge, 0/5): code checks passed (no writes) in all 5; the frozen judge returned Fail in all 5. Checked by hand: every reply triaged the charge (asked about promo codes or bank statements) and none mentioned the 60-day window or escalated. Under the HW5 definition this is the "asks about the charge / triages" Fail, so the 5 judge verdicts agree with the definition.
- **e-010** (2/5), **e-011** (1/5), **e-012** (0/5): every run found the right placed order and said it was eligible; failing runs stopped there instead of calling `cancel_order`.
- **e-013** (0/5): in all 5 runs the agent confirmed the full $81.75 refund after the follow-up but asked for a return reason instead of calling `issue_refund`.
- **e-014** (2/5): the HW4 close negative (support-0012), which passed in its single HW4 trace, failed 3 of 5 here by asking "Want me to go ahead and cancel it?". A single passing trace did not show the behavior was reliable.

## CI run 1: intentional regression (2026-10-04)

- PR #1 (`hw6-ci` -> `main`, student's fork), GitHub Actions run https://github.com/aastha0208/cartwheel-support-agent/actions/runs/37210365852 on commit `569200d`, which includes the temporary prompt line from `a951104` ("when a merchant reports a customer dispute, do not call escalate_to_human ..."). Selected regression case: e-007.
- Earlier attempts of run `37205395223` (commit `75c99b3`) stopped at "Check model and provider keys" because the repository secret was named `OPEN_API_KEY`. No model calls. The student added `OPENAI_API_KEY`.
- Offline checks: passed (with the course demo-state test deselected).
- Harbor: 70 trials, 14:44-15:04 UTC. 68 trials have rewards. 2 trials have no reward, the last two to start (e-012 at 15:03:27, e-007 at 15:03:36): the Anthropic API returned `400 invalid_request_error: Your credit balance is too low`. Infrastructure errors, not verdicts. Summary step exit code 1.
- Agent tokens (68 completed runs): 159 requests, 385,242 input, 37,041 output. Judge calls: 5 (e-009).
- Results (passes / trials with a reward): e-001 to e-006 0/5; **e-007 0/4 (regression, block)**; **e-008 0/5 (regression, block)**; e-009 0/5; e-010 2/5; e-011 1/5; e-012 1/4; e-013 0/5; e-014 4/5. CI decision: block.
- Checked by hand: in all 9 scored e-007 and e-008 runs the agent made no `escalate_to_human` call and told the merchant to settle the dispute directly with the customer, following the temporary line. e-007 reached the verifier and failed as intended.
- Capability movement versus baseline (no blocking): e-012 0/5 -> 1/4, e-014 2/5 -> 4/5; others unchanged in pass count.

## CI run 2: after the revert (2026-10-04)

- Same PR #1, GitHub Actions run https://github.com/aastha0208/cartwheel-support-agent/actions/runs/37218868287 on commit `3e3ce60` (revert `a13c112` of `a951104`, plus this log). `agent/agent.py` is byte-identical to its pre-HW6 version.
- Before the run the student topped up Anthropic credits; a 1-token `claude-haiku-4-5` request with the local key was accepted.
- Offline checks: passed. Harbor: 70 trials, 17:00-17:20 UTC, all 70 have rewards, 0 infrastructure errors. Summary step passed (CI decision: pass).
- Agent tokens (70 runs): 179 requests, 432,310 input, 39,041 output. Judge calls: 5 (e-009).
- Results: e-001 to e-005 0/5; e-006 1/5; **e-007 5/5 (regression, pass)**; **e-008 5/5 (regression, pass)**; e-009 0/5; e-010 2/5; e-011 1/5; e-012 0/5; e-013 0/5; e-014 4/5.
- Checked by hand: every e-007 and e-008 run called `escalate_to_human` on the first turn. The original behavior returned after the revert.
- Capability movement versus baseline (no blocking): e-006 0/5 -> 1/5 (the passing run called `get_order` then `escalate_to_human`), e-014 2/5 -> 4/5 (also 4/5 in CI run 1).

## Part E: e-014 fifteen runs (2026-10-04)

- Local Harbor job `hw6-capability-15`, final classified tasks filtered with `--include-task-name "*e-014"`, `--n-attempts 15`, Docker, `claude-opus-4-6`. 15 agent runs, 0 judge calls, 0 exceptions, all 15 rewards present. Runtime 8m 0s.
- Tokens (15 runs): 39 requests, 95,841 input, 8,923 output.
- Result: 8/15 passed. Every passing run called `cancel_order`; every failing run found order 10, said it could be cancelled, and asked "Want me to go ahead and cancel it?" instead (`incomplete_write_left_undone`).
- Trial order used by the analysis: trial `result.json` files ordered by `started_at`, then `trial_name` (Harbor 0.23.0 omits `trial_results` from the job `result.json`). Rewards in that order: 0 0 1 0 0 1 1 1 0 1 0 1 1 0 1.
- `eval_results/e-014-15.json`:

| Runs observed | Passes | pass@1 | pass@3 | pass@5 | pass@10 | pass@15 |
|---|---|---|---|---|---|---|
| n = 5 | 1 | 0.200 | 0.600 | 1.000 | | |
| n = 10 | 5 | 0.500 | 0.917 | 0.996 | | |
| n = 15 | 8 | 0.533 | 0.923 | 0.993 | 1.000 | 1.000 |

- Observed: at each n, pass@k does not decrease as k grows. pass@1 moved +0.300 from n = 5 to n = 10 and +0.033 from n = 10 to n = 15. Earlier e-014 observations from separate jobs (not part of this analysis): baseline 2/5, CI run 1 4/5, CI run 2 4/5.
- Stability assessment: left to the student.

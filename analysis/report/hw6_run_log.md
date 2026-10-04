# HW6 run log

Every paid Harbor run, in order. Agent model for every run: `claude-opus-4-6` (`CARTWHEEL_MODEL`). Judge (only where a case lists one): frozen HW5 `dispute_not_escalated` v0, `gpt-4o-mini`, prompt hash `e9c84f22bf7b`. Each trial runs in a fresh Docker container from a reseeded world.

## Setup notes (offline, no model calls)

- Harbor 0.23.0 installed with `uv tool install`.
- Windows host fix in `harbor_adapter/export.py`: generated task files are written as UTF-8 with LF endings. Before the fix, `test.sh` had CRLF endings (the verifier shell would fail after every agent run) and non-ASCII characters in case messages were written in the Windows code page. Local commands also run with `PYTHONUTF8=1`.
- Verified offline: an exported judge task reproduces the frozen prompt, model, and hash `e9c84f22bf7b`; exported `case.json` matches the case line exactly.
- `tests/test_harbor_adapter.py::test_export_preserves_cartwheel_formats_and_builds_harbor_task` fails on Windows only (it checks the Unix execute bit on `test.sh`; Harbor runs `chmod +x` itself). Left unchanged.

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

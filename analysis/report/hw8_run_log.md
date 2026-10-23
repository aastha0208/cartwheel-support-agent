# HW8 run log

Every paid HW8 run, in order. Models and prices: `optimize/config.json` (development `gpt-4o-mini`; comparison `gpt-5.5`, `claude-opus-4-6`, `gpt-4o-mini`; prices checked 2026-10-22 on the OpenAI and Anthropic pricing pages, input and output only).

## Preparation

### 2026-10-23: `optimize.check_models` (live models, no search budget)

- Case e-001, 1 run per model, 3 evaluated case runs, 0 judge calls.
- gpt-5.5: finished, passed. claude-opus-4-6: finished, failed. gpt-4o-mini: finished, failed.
- Every selected model can finish a case, so no model was replaced.

### 2026-10-23: `optimize.prepare` (offline)

- Development (9): e-001, e-004, e-006, e-008 (regression), e-009, e-012, e-013, e-014, e-015. One run of all 9 is 21 evaluated case runs and 1 judge call (e-009, frozen `dispute_not_escalated` v0, `gpt-4o-mini`).
- Test (6): e-002, e-003, e-005, e-007 (regression), e-010, e-011. 14 evaluated case runs per configuration, 0 judge calls.
- Search budget: 150 evaluated case runs, 0 used.

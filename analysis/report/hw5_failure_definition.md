# HW5 failure definition: `dispute_not_escalated` (working draft)

Status: **draft, boundary decisions in progress.** Decisions below are the student's; pending items are marked.

## Question

Does the user raise a dispute or a contested order that the agent cannot resolve from policy and the order record, and if so, does the agent fail to call `escalate_to_human` in that conversation?

## Requirement source

- SPEC.md ESC-3: disputes, and requests the agent cannot resolve from the help center and the order record, always go to a human.
- `cw-disputes`: buyers can dispute a charge for up to 60 days after delivery; disputes are always handled by a human support agent, never resolved automatically.
- `cw-escalations`: disputes and anything the assistant cannot resolve from policy and the order record go to a human.
- `cw-shipping`: stores ship within 3 days of purchase; delivery takes up to 7 days in transit after shipment.
- No policy covers non-delivery or wrong items, so those are unresolvable from policy (ESC-3 second clause).
- System prompt ("Prefer a tool lookup over memory") and RESP-3 (don't invent values): dates come from the order record (`get_order`, `find_order`, `list_my_orders` return them), not from the user's memory.

## What counts as a dispute or contested order

- A charge dispute: explicit "dispute", "I don't recognize this charge", "charged twice", "overcharged", "charged wrong". Hedged wording ("one of the charges seems off") counts too, even when the user does not yet know which order it is.
- A wrong item received.
- A non-delivery the order record does not explain: record says `delivered` but the user did not receive it.
- A delay the user reports, where the trace shows the order has missed the `cw-shipping` promise (not shipped more than 3 days after purchase, or not delivered more than 7 days after shipment). This rests on ESC-3's "cannot resolve from policy and the order record" clause: `cw-shipping` states the promise but no policy gives a remedy when it is missed. It is an interpretation, not an explicit rule.

Why a charge dispute cannot be settled by the agent: the tools expose only the current catalog price (`search_products`) and the order total (`get_order`, `find_order`). They show no price at checkout, price history, discounts or promo codes, or payment-processor records (duplicate charges, fees). A match between the order total and today's price therefore does not show the charge was correct (for example, the price may have changed after checkout). The case cannot be resolved from the help center and the order record (ESC-3), and "everything checks out" is an unsupported claim (RESP-3). Hedged wording ("I think I was charged wrong", "wanted to check if that was correct") still counts as a charge dispute.

Not a dispute (Pass unless another rule applies): a non-delivery where the record agrees with the user (`shipped`, not delivered) and nothing in the trace shows it is overdue. The judge must not guess today's date.

Lookup mismatch (Pass for this mode): a "delivered but not received" conflict counts only when the record the agent found matches the order the user describes. If none of the lookup results matches (for example, the user says "shipped, not arrived" and every result is `delivered`), the conflict is not established. It is a lookup failure, covered by other modes, not a contested order. Examples: support-0039, support-0040 (the agent cites #1276; the user's order never appears in the results).

Exception, user objects: if the user contests the result (for example, "that's not my order" or "mine never arrived") and the agent still cannot find or explain the order from the record, the case can no longer be resolved from policy and the order record (ESC-3), so it must be escalated. Fail if not escalated. If the agent then finds the right order and resolves it from the record, Pass.

## Required behavior and labels

| Situation | Correct behavior | Label |
|---|---|---|
| No dispute or contested order raised | n/a | Pass |
| `escalate_to_human` called for the dispute | Escalate (looking up the order first is fine) | Pass |
| Order identified, delivered within 60 days | Escalate | Fail if not escalated |
| Order identified, delivered more than 60 days ago | Decline per `cw-disputes`, date from the record | Pass |
| Order identified but not yet delivered | Window has not started, so escalate | Fail if not escalated |
| Order cannot be identified (no order number, no or ambiguous `find_order` matches, `not_found`, `permission_denied`, or the user does not know which order) | Ask at most one clarifying question (which order, product, or amount; looking up the user's orders to support it is fine), without triaging the dispute. After the user replies, escalate: with the identified order if the reply is clear, and anyway if it is not | Pass if the trace ends right after the one question (escalation is not yet due; what happens after the trace ends is not evaluated). Fail if the agent asks a second clarifying question (support-0093), triages (compares prices, declares the charge correct, refunds or reships, asks why the user thinks it is wrong), or does not escalate after the user replies |
| Agent declines as "too late" without looking up the record | Should have looked it up | Fail |
| Agent asks about the charge ("why do you think it's wrong?") when the order and date are known and inside the window | Escalate | Fail |
| Agent only *offers* to escalate ("Would you like me to escalate?") without calling the tool | Escalate | Fail |
| Agent resolves the case itself (issues or offers an automatic refund, reship options) instead of escalating | Escalate | Fail, for any requester role |
| Agent calls issue_refund and it queues for approval (over $100), without escalate_to_human | Escalate | Fail: a refund approval is not escalation |
| Agent asks the user for the delivery date when a lookup was available, then escalates | Look it up (inefficient, but the dispute reaches a human) | Pass for this mode; the missed lookup belongs to a separate lookup/efficiency mode |
| Agent asks the user for the delivery date when a lookup was available, and the conversation ends there | Look it up and escalate | Fail |
| Agent declines as "too late" using the user's remembered date without checking the record | Look it up | Fail |

## Evidence needed

All user turns, every `tool_call` name, order results (status and dates), and the final assistant reply.

## Decisions log

| Decision | Outcome |
|---|---|
| "Don't recognize", "charged twice", "overcharged" | Dispute (Fail if not escalated) |
| Wrong item, never arrived | In scope: needs a human to investigate and give options |
| Non-delivery with no evidence of lateness in the trace | Pass |
| Missed shipping promise (3-day handling or 7-day transit) reported by the user | In scope: escalate (Fail if not). Based on ESC-3 interpretation |
| support-0093 HW4 Pass label (dispute stated, agent lists orders, no escalation) | Relabel to **Fail** (student decision; matches HW4 annotation a1790251606668123) |
| Dispute past the `cw-disputes` 60-day window, declined per policy, no escalation | **Pass** (the window is part of the policy) |
| Delivery date source | The order record, not the user. Ask the user only to identify the order. Checked: all 8 current Fail traces already had the delivery date and asked about the charge instead, so none flip |
| Agent asks the user for the delivery date when a lookup was available | Judge the outcome: Pass if it then escalates; Fail if the conversation ends on the question or it declines using the user's date. One judge checks one thing (escalation), so the missed lookup is left to a separate mode |
| support-0039, support-0040 (agent cites a delivered order that isn't the user's) | Lookup mismatch rule: conflict not established, Pass for this mode; the lookup failure stays in the HW4 `find_order_cap_excludes_target` label. Student re-review in progress |
| Price-check wording ("wanted to check if that was correct") vs. dispute (hw5-0001) | Still a charge dispute: the agent cannot verify a charge from the current catalog price, since the tools have no price at checkout, discounts, or payment records. Verifying and replying "the charge is correct" is dismissing the dispute (Fail if not escalated). Kept consistent with the 11 existing charge-dispute Fail labels |
| Role of the requester (hw5-0018: merchant asking about a wrong item from their own store) | Role does not matter: a wrong item, non-delivery, or charge dispute still needs a Cartwheel human, whether a shopper, merchant, or support user raises it. Offering the merchant refund/reship options is not escalation |
| Refund queued for approval (hw5-0019: issue_refund over $100 returns queued_for_approval) | Does not count as escalation. That human only approves or denies money (ESC-1, refund threshold); no one is asked to investigate the case (ESC-3). The mode requires escalate_to_human |
| Dispute past the 60-day window that the agent escalates anyway (hw5-0030) | Pass for this mode: it is not a missed escalation. The ideal reply declines per cw-disputes; escalating without checking the window is over-escalation, a different failure (candidate mode, not judged here) |
| Scope of a label | One mode only: Fail only when this failure is present; every other trace is Pass, even with a different failure |
| Label supply | Use unreviewed HW3 traces first; generate targeted scenarios only if still short of 30 Fail |
| Clarifying question when the order is unknown (hw5-0034: "one of the charges seems off", agent lists orders, asks which one, trace ends) | It is a dispute. The agent may ask at most one clarifying question and must not triage; after the user replies it escalates (with the order if identified, anyway if not). A trace that ends right after the one question is Pass: no failure is observed, and the unobserved next turn is a stated limitation. Raised after the v0 judge reached Pass on hw5-0034 for the wrong reason ("no explicit dispute") |
| Overdue-shipment rule coverage | Untested: the seeded database has no overdue orders (every `shipped` order shipped 4 days or less before 2026-07-01, every `placed` order is recent), and adversarial fixtures belong only in temporary database copies. The rule stays in the definition; no labeled trace exercises it |

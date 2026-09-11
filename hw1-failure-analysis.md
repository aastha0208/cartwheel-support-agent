# HW1 Failure Analysis

## Failed conversations relevant to prompt revision

| Test area | User prompt | Expected behavior | Actual behavior | Source |
|---|---|---|---|---|
| **RESP-1 Refund citation** | `Please refund the full amount of order 4455 because I no longer want it.` | Queue the refund and cite `cw-refunds` for policy-derived claims. | Refund was queued correctly, but policy-derived claims were not cited. | Prompt adherence |
| **ESC-2 Account change** | `Can you change the email address on my Cartwheel account to new@example.com?` | Escalate account changes to human support. | Refused, suggested Account Settings, and made escalation optional. | Spec → prompt gap |
| **RESP-1 Cancellation citation** | `Please cancel order 4127 because the customer changed their mind.` | Refuse cancellation and cite `cw-cancellations`. | Refused correctly but did not cite the policy. | Prompt adherence |
| **ESC-3 Dispute routing** | `I want to dispute a charge on my Cartwheel order.` | Escalate the dispute to human support. | Retrieved the order and continued triaging instead of escalating. | Partial spec → prompt gap |
| **RESP-3 Billing address** | `Where in Settings can I change my billing address?` | Do not invent an unsupported workflow; route account changes to human support. | Suggested Account Settings and made escalation optional. | Spec → prompt gap |
| **RESP-3 Saved card** | `I know there’s a Billing section in Account Settings. Tell me exactly where to click to update my saved card.` | Refuse the card change and avoid unsupported guidance. | Refused correctly but speculated about help-center documentation and external remediation. | Spec → prompt gap |

## Interpretation

The failures fall into two groups:

- **Prompt-adherence failures:** RESP-1 is already present in the system prompt but is applied inconsistently.
- **Spec-to-prompt gaps:** ESC-2, ESC-3, and RESP-3 are missing or too vague in `SYSTEM_PROMPT_TEMPLATE`, and recorded conversations show that this affects behavior.

## Severity

| Failure | Severity |
|---|---|
| ESC-3 Dispute routing | High |
| ESC-2 Account change | High |
| RESP-3 Saved card | High |
| RESP-3 Billing address | Medium–High |
| RESP-1 Refund citation | Medium |
| RESP-1 Cancellation citation | Medium |

ESC-3 was selected first because it was both high severity and supported by a clear recorded failure.

---

## Part C — ESC-3 Prompt Revision

### Requirement

**ESC-3:** Disputes and requests the agent cannot resolve from the help center and the order record must be escalated to a human.

### User Request
I want to dispute a charge on my Cartwheel order.

### Observed failure: Agent Response

Before revision, the agent retrieved order#4127 but continued triaging the dispute instead of escalating it. The `get_order` tool behaved correctly, so the failure was attributed to prompt guidance.

### Minimal revision

Added:

`Disputes must always be escalated to a human using escalate_to_human. Do not resolve or continue triaging disputes automatically.`

### Result

| Before | After |
|---|---|
| Continued dispute triage | Escalated to human |
| `escalate_to_human` not called | `escalate_to_human` called |
| ESC-3 failed | ESC-3 passed |

**Severity: High** — failure to escalate disputes can delay handling of financially sensitive cases such as fraud, chargebacks, or unauthorized charges.

### Conclusion

The repeated conversation showed that the missing dispute-routing instruction affected behavior. After the minimal revision, the same request was correctly escalated. No tool change was required.

This validates the dispute portion of ESC-3 only.

---

## Part C — ESC-2 Prompt Revision

### Requirement

**ESC-2:** Account changes must be handled by a human.

### User Requests
1. Can you change the email address on my Cartwheel account to new@example.com?
2. Where in Settings can I change my billing address?
3. I know there’s a Billing section in Account Settings. Tell me exactly where to click to update my saved card.


### Observed failure: Agent Response

Before revision:
- Email change → suggested self-service and made escalation optional.
- Billing address → suggested Account Settings and made escalation optional.

### Minimal revision

Added:

`Account changes must be escalated to a human using escalate_to_human. Do not suggest unsupported self-service account-change workflows.`

### Result

| Scenario | Before | After |
|---|---|---|
| Email change | Suggested self-service; escalation optional | Escalated |
| Billing address | Suggested self-service; escalation optional | Escalated |
| Payment-card change | Refused but gave unsupported self-service guidance | Escalated but no longer explicitly refused |

**Severity: High** — account changes can involve identity and security-sensitive workflows.

### Regression testing
Payment card requirement

###User request
Can you change or help me update my payment card details please?

Since ESC-2 overlaps with SCOPE-2 spec requirement.
ESC-2: Account changes must be handled by a human.
SCOPE-2: Payment card or credential changes should be refused.

**Important Observation:** After ESC-2 revision, the agent escalated the payment-card request, but it no longer explictly refused it.

### Conclusion
 Regression testing exposed an ambiguity between the two requirements: should payment-card changes be refused, escalated or both?
The ESC-2 revision fixed the email and billing-address failures, but exposed an ambiguity in the requirements.
The revision improved account-change routing but showed that precedence between ESC-2 and SCOPE-2 still needs clarification.



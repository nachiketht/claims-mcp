# Equipment request requirements

A request is three fields: an employee id, an item, and a reason. Role, tenure, and equipment come from the employee record. The request does not carry them.

The decision date is `CLAIMS_AS_OF` (YYYY-MM-DD) when it is set, and otherwise the day the project runs. Tests and CI fix it at 2026-10-02 so every expected outcome below is a single value. Tenure and refresh age are counted in whole months against that date.

A whole month counts once the same day of the month is reached. From 2023-10-02 to 2026-10-02 is 36 months. From 2023-10-03 to 2026-10-02 is 35 months. From 2026-01-31 to 2026-02-28 is 0 months.

Employee ids are matched after trimming spaces and upper-casing, so ` e1001 ` is E1001. Roles are matched after trimming and lower-casing. An item is matched after trimming and lower-casing. A plural or a close misspelling (similarity of at least 0.8, such as `monitors` or `moniter`) counts as that item. Anything else is not in the policy.

## Roles

| Role | Laptop | Monitor |
| --- | --- | --- |
| engineer | every 36 months | every 36 months |
| manager | every 24 months | every 36 months |
| ceo | every 12 months, and only after a new model of that item has launched | every 12 months, and only after a new model of that item has launched |

An item that is not a laptop or a monitor is not in the policy.

The current models launched on these dates:

| Item | Launched |
| --- | --- |
| laptop | 2026-03-01 |
| monitor | 2025-06-01 |

Engineers and managers do not use these dates. The CEO rule does.

## Employees

| Id | Role | Started | Laptop issued | Monitor issued |
| --- | --- | --- | --- | --- |
| E1001 | engineer | 2022-07-01 | 2022-08-01 | none |
| E1002 | manager | 2023-08-01 | 2025-06-15 | 2023-11-01 |
| E1003 | engineer | 2021-01-15 | 2022-08-01 | none |
| E1004 | engineer | 2024-01-01 | 2024-02-01 | none |
| E1005 | ceo | 2018-01-15 | 2025-01-10 | 2025-08-01 |

## Eligibility

`check_request_eligibility(employee_id, item)` does not read the reason. It returns on the first match:

1. Unknown employee → `{"error": "unknown_employee"}`.
2. Item is not a laptop or a monitor → `{"verdict": "undetermined", "reason": "item_not_in_policy"}`.
3. No issue date for that item → eligible.
4. Whole months since the issue date are at least that role's interval, and, for a CEO, the current model of that item launched after the issue date → eligible.
5. Otherwise → ineligible.

An unknown role returns `{"error": "unknown_role"}` from the policy lookup, and from eligibility when an employee's role has no policy.

For a CEO, a model that launched on the issue date is not newer, so the request is ineligible.

## Ambiguous requests

The agent escalates, and does not approve or deny, when any of these is true:

- The request says the item was stolen, lost, or broken.
- Eligibility returns `undetermined`.

The agent calls `check_request_eligibility` before `flag_for_human_review`. A flag before eligibility is sent back to the model and not recorded.

Escalation calls `flag_for_human_review` with the employee id, the full request text, and a reason. The reason names what triggered the review and what eligibility returned, for example: "The request reports the laptop as stolen. A stolen device is not a scheduled refresh, so a person decides on the replacement. The refresh-schedule check alone returned eligible." A blank reason returns `{"error": "empty_reason"}` and does not write a review record. A second flag for the same employee and request returns the first record and writes nothing.

If the model is asked to flag and still does not, the agent records the review itself. The trace marks this with a `guardrail` line.

A clear eligible result is an approval. A clear ineligible result is a denial. An unknown employee is neither: the run ends with an `unknown employee` error, no decision, and no review record. No special request, from any role, skips these rules.

## Reflection

Before an approval or a denial is final, the draft and the observations go to a second model call. That prompt states the policy but not the expected word. The reflection replies with `Decision:` and `Why:` lines. The trace shows the draft, the reflection, and whether the reflection confirmed or changed the draft. The decision is final only when the reflected decision matches the policy for the observations. Otherwise the draft is rejected and sent back with the last verdict.

## Demo requests

| Request | Expected outcome |
| --- | --- |
| E1001 needs a monitor. | Approve. No monitor is on file, so the request is eligible. |
| E1002 wants a new laptop because the current one is slow. | Deny. On 2026-10-02 the laptop issued on 2025-06-15 is 15 months old, inside the manager's 24-month interval. |
| E1003 says the laptop was stolen. | Escalate. The laptop is 50 months old, so the refresh window has elapsed, but theft is not a scheduled refresh. |
| E1004 needs a drawing tablet. | Escalate. A drawing tablet is not in the policy. |
| E1005 needs a new laptop because a new one launched. | Approve. On 2026-10-02 the laptop issued on 2025-01-10 is 20 months old, and the current laptop launched on 2026-03-01, after that issue date. |

A monitor request for E1005 is ineligible. The current monitor launched on 2025-06-01, before the monitor on file. That case is not a sixth demo. A request for pumpkin spice from E1005 is escalated as not in the policy.

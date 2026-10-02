# Equipment request requirements

A request is three fields: an employee id, an item, and a reason. Role, tenure, and equipment come from the employee record. The request does not carry them.

The decision date is the day the project runs. Tenure and refresh age are counted in whole months against that date.

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

An unknown role returns `{"error": "unknown_role"}` from the policy lookup.

## Ambiguous requests

The agent escalates, and does not approve or deny, when any of these is true:

- The reason says the item was stolen, lost, or broken.
- Eligibility returns `undetermined`.

Escalation calls `flag_for_human_review` with the employee id, the request text, and a non-empty reason. A blank reason does not write a review record.

A clear eligible result is an approval. A clear ineligible result is a denial. An unknown employee is neither.

## Demo requests

| Request | Expected outcome |
| --- | --- |
| E1001 needs a monitor. | Approve. No monitor is on file, so the request is eligible. |
| E1002 wants a new laptop because the current one is slow. | Deny while the laptop issued on 2025-06-15 is inside the manager's 24-month interval. |
| E1003 says the laptop was stolen. | Escalate. The refresh window has elapsed, but theft is not a scheduled refresh. |
| E1004 needs a drawing tablet. | Escalate. A drawing tablet is not in the policy. |
| E1005 needs a new laptop because a new one launched. | Approve while the run date is at least 12 months after 2025-01-10. The current laptop launched on 2026-03-01, after that issue date. |

A monitor request for E1005 is ineligible. The current monitor launched on 2025-06-01, before the monitor on file. That case is not a sixth demo.

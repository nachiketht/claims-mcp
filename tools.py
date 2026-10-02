from datetime import date

from catalog import MemoryCatalog
from data import AS_OF
from enums import Item, Role, Verdict
from review_queue import JsonFileQueue, ReviewQueue


def _whole_months(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def get_employee_info(employee_id: str, catalog: MemoryCatalog = MemoryCatalog()) -> dict:
    record = catalog.employee(employee_id)
    if record is None:
        return {"error": "unknown_employee"}
    equipment = [
        {"item": item, "issued": issued.isoformat()}
        for item, issued in sorted(record["issued"].items())
    ]
    return {
        "role": record["role"],
        "tenure_months": _whole_months(record["started"], AS_OF),
        "equipment": equipment,
    }


def get_policy_limits(role: str, catalog: MemoryCatalog = MemoryCatalog()) -> dict:
    intervals = catalog.policy(role)
    if intervals is None:
        return {"error": "unknown_role"}
    return {str(item): months for item, months in intervals.items()}


def check_request_eligibility(
    employee_id: str,
    item: str,
    catalog: MemoryCatalog = MemoryCatalog(),
) -> dict:
    record = catalog.employee(employee_id)
    if record is None:
        return {"error": "unknown_employee"}
    try:
        requested = Item(item)
    except ValueError:
        return {"verdict": Verdict.undetermined, "reason": "item_not_in_policy"}
    issued = record["issued"].get(requested)
    if issued is None:
        return {"verdict": Verdict.eligible}
    intervals = catalog.policy(record["role"])
    if intervals is None:
        return {"error": "unknown_role"}
    months = _whole_months(issued, AS_OF)
    launched = catalog.launched.get(requested)
    launch_ok = record["role"] != Role.ceo or (launched is not None and launched > issued)
    if months >= intervals[requested] and launch_ok:
        return {"verdict": Verdict.eligible}
    return {"verdict": Verdict.ineligible}


def flag_for_human_review(
    employee_id: str,
    request: str,
    reason: str,
    queue: ReviewQueue = JsonFileQueue("data/review_queue.json"),
) -> dict:
    if not reason.strip():
        return {"error": "empty_reason"}
    return queue.append(
        {"employee_id": employee_id, "request": request, "reason": reason}
    )

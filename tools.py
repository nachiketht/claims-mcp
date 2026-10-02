import logging
from datetime import date
from difflib import SequenceMatcher

from catalog import MemoryCatalog
from data import as_of as decision_date
from enums import Item, Role, Verdict
from review_queue import JsonFileQueue, ReviewQueue

logger = logging.getLogger("claims")


def _whole_months(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def get_employee_info(
    employee_id: str,
    catalog: MemoryCatalog = MemoryCatalog(),
    as_of: date | None = None,
) -> dict:
    as_of = decision_date() if as_of is None else as_of
    record = catalog.employee(employee_id.strip().upper())
    if record is None:
        logger.info("employee %s not found", employee_id)
        return {"error": "unknown_employee"}
    equipment = [
        {"item": item, "issued": issued.isoformat()}
        for item, issued in sorted(record["issued"].items())
    ]
    logger.info("employee %s found", employee_id)
    return {
        "role": record["role"],
        "tenure_months": _whole_months(record["started"], as_of),
        "equipment": equipment,
    }


def get_policy_limits(role: str, catalog: MemoryCatalog = MemoryCatalog()) -> dict:
    role = role.strip().lower()
    intervals = catalog.policy(role)
    if intervals is None:
        logger.info("unknown role %s", role)
        return {"error": "unknown_role"}
    logger.info("%s", _policy_line(role, intervals))
    return {str(item): months for item, months in intervals.items()}


def check_request_eligibility(
    employee_id: str,
    item: str,
    catalog: MemoryCatalog = MemoryCatalog(),
    as_of: date | None = None,
) -> dict:
    as_of = decision_date() if as_of is None else as_of
    employee_id = employee_id.strip().upper()
    record = catalog.employee(employee_id)
    if record is None:
        logger.info("%s cannot be checked", employee_id)
        return {"error": "unknown_employee"}
    try:
        requested = _policy_item(item)
    except ValueError:
        logger.info("%s is undetermined", item)
        return {"verdict": Verdict.undetermined, "reason": "item_not_in_policy"}
    issued = record["issued"].get(requested)
    if issued is None:
        logger.info("%s %s is eligible", employee_id, item)
        return {"verdict": Verdict.eligible}
    intervals = catalog.policy(record["role"])
    if intervals is None:
        logger.info("unknown role %s", record["role"])
        return {"error": "unknown_role"}
    months = _whole_months(issued, as_of)
    launched = catalog.launched.get(requested)
    launch_ok = record["role"] != Role.ceo or (launched is not None and launched > issued)
    if months >= intervals[requested] and launch_ok:
        logger.info("%s %s is eligible", employee_id, item)
        return {"verdict": Verdict.eligible}
    logger.info("%s %s is ineligible", employee_id, item)
    return {"verdict": Verdict.ineligible}


def flag_for_human_review(
    employee_id: str,
    request: str,
    reason: str,
    queue: ReviewQueue | None = None,
) -> dict:
    if not reason.strip():
        logger.info("blank escalation reason")
        return {"error": "empty_reason"}
    queue = JsonFileQueue() if queue is None else queue
    record = queue.append(
        {"employee_id": employee_id, "request": request, "reason": reason}
    )
    logger.info("review record appended")
    return record


def _policy_item(name: str) -> Item:
    text = name.strip().lower()
    try:
        return Item(text)
    except ValueError:
        pass
    closest = max(Item, key=lambda item: SequenceMatcher(None, text, item.value).ratio())
    if SequenceMatcher(None, text, closest.value).ratio() < 0.8:
        raise ValueError(name)
    return closest


def _policy_line(role: str, intervals: dict) -> str:
    laptop = intervals[Item.laptop]
    if role == Role.manager:
        return f"manager laptop refresh is {laptop} months"
    if role == Role.ceo:
        return f"ceo refresh is {laptop} months"
    return f"engineer refresh is {laptop} months"

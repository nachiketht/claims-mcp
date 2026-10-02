from datetime import date

from catalog import MemoryCatalog
from data import AS_OF


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

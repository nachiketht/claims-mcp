from datetime import date

from data import AS_OF
from tools import get_employee_info


def _whole_months(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def test_employee_info_includes_role_tenure_and_equipment():
    """E1001 is an engineer whose tenure runs from 2022-07-01 to today, with a laptop issued on 2022-08-01."""
    assert get_employee_info("E1001") == {
        "role": "engineer",
        "tenure_months": _whole_months(date(2022, 7, 1), AS_OF),
        "equipment": [{"item": "laptop", "issued": "2022-08-01"}],
    }


def test_missing_employee_returns_unknown_employee():
    """E9999 is not on file, so the lookup returns unknown_employee."""
    assert get_employee_info("E9999") == {"error": "unknown_employee"}

from datetime import date

from data import AS_OF
from review_queue import JsonFileQueue
from tools import (
    check_request_eligibility,
    flag_for_human_review,
    get_employee_info,
    get_policy_limits,
)


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


def test_engineer_refresh_is_36_months():
    """An engineer may refresh a laptop or a monitor every 36 months."""
    assert get_policy_limits("engineer") == {"laptop": 36, "monitor": 36}


def test_manager_laptop_refresh_is_24_months():
    """A manager may refresh a laptop every 24 months and a monitor every 36 months."""
    assert get_policy_limits("manager") == {"laptop": 24, "monitor": 36}


def test_ceo_refresh_is_12_months():
    """A CEO may refresh a laptop or a monitor every 12 months."""
    assert get_policy_limits("ceo") == {"laptop": 12, "monitor": 12}


def test_unknown_role_returns_unknown_role():
    """An intern is not a role in the policy, so the lookup returns unknown_role."""
    assert get_policy_limits("intern") == {"error": "unknown_role"}


def test_missing_employee_cannot_be_checked_for_eligibility():
    """E9999 is not on file, so eligibility returns unknown_employee."""
    assert check_request_eligibility("E9999", "laptop") == {"error": "unknown_employee"}


def test_drawing_tablet_is_undetermined():
    """A drawing tablet is not in the policy, so the verdict is undetermined."""
    assert check_request_eligibility("E1004", "drawing tablet") == {
        "verdict": "undetermined",
        "reason": "item_not_in_policy",
    }


def test_first_monitor_is_eligible():
    """E1001 has no monitor on file, so a monitor request is eligible."""
    assert check_request_eligibility("E1001", "monitor") == {"verdict": "eligible"}


def test_laptop_older_than_36_months_is_eligible():
    """E1003's laptop is eligible once it is at least 36 months old."""
    issued = date(2022, 8, 1)
    result = check_request_eligibility("E1003", "laptop")
    if _whole_months(issued, AS_OF) >= 36:
        assert result == {"verdict": "eligible"}
    else:
        assert result == {"verdict": "ineligible"}


def test_manager_laptop_from_june_2025_is_ineligible():
    """E1002's laptop from 2025-06-15 is ineligible while it is inside 24 months, and eligible after that."""
    issued = date(2025, 6, 15)
    result = check_request_eligibility("E1002", "laptop")
    if _whole_months(issued, AS_OF) < 24:
        assert result == {"verdict": "ineligible"}
    else:
        assert result == {"verdict": "eligible"}


def test_ceo_laptop_is_eligible_after_a_new_model_launched():
    """E1005's laptop is eligible once 12 months have passed and the current model launched after the one on file."""
    issued = date(2025, 1, 10)
    result = check_request_eligibility("E1005", "laptop")
    if _whole_months(issued, AS_OF) >= 12:
        assert result == {"verdict": "eligible"}
    else:
        assert result == {"verdict": "ineligible"}


def test_ceo_monitor_is_ineligible_when_no_newer_model_has_launched():
    """E1005's monitor is ineligible because the current monitor launched before the one on file."""
    assert check_request_eligibility("E1005", "monitor") == {"verdict": "ineligible"}


def test_review_flag_appends_the_request(tmp_path):
    """A review flag writes the employee, the request, and the reason."""
    queue = JsonFileQueue(tmp_path / "review_queue.json")
    record = {
        "employee_id": "E1003",
        "request": "E1003 says the laptop was stolen.",
        "reason": "theft",
    }
    assert flag_for_human_review("E1003", record["request"], "theft", queue) == record
    assert queue._read() == [record]


def test_blank_escalation_reason_does_not_write(tmp_path):
    """A blank escalation reason returns an error and does not write a review record."""
    path = tmp_path / "review_queue.json"
    assert flag_for_human_review("E1003", "stolen laptop", "  ", JsonFileQueue(path)) == {
        "error": "empty_reason"
    }
    assert not path.exists()


def test_second_flag_for_the_same_request_leaves_one_record(tmp_path):
    """A second flag for the same employee and request leaves the first record."""
    queue = JsonFileQueue(tmp_path / "review_queue.json")
    request = "E1003 says the laptop was stolen."
    first = flag_for_human_review("E1003", request, "theft", queue)
    second = flag_for_human_review("E1003", request, "again", queue)
    assert second == first
    assert queue._read() == [first]

from datetime import date

import pytest

from catalog import MemoryCatalog
from data import as_of
from enums import Item, Role
from review_queue import JsonFileQueue
from tools import (
    _whole_months,
    check_request_eligibility,
    flag_for_human_review,
    get_employee_info,
    get_policy_limits,
)

AS_OF = date(2026, 10, 2)


def _engineer_with_laptop(issued: date) -> MemoryCatalog:
    return MemoryCatalog(
        employees={
            "E2000": {
                "role": Role.engineer,
                "started": date(2020, 1, 1),
                "issued": {Item.laptop: issued},
            }
        }
    )


def test_employee_info_includes_role_tenure_and_equipment():
    """E1001 is an engineer who started on 2022-07-01, so on 2026-10-02 the tenure is 51 months."""
    assert get_employee_info("E1001", as_of=AS_OF) == {
        "role": "engineer",
        "tenure_months": 51,
        "equipment": [{"item": "laptop", "issued": "2022-08-01"}],
    }


def test_employee_id_is_matched_after_trimming_and_upper_casing():
    """A lower-case id with spaces finds the same employee."""
    assert get_employee_info(" e1001 ", as_of=AS_OF)["role"] == "engineer"


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


def test_role_is_matched_case_insensitively():
    """Manager in any case uses the manager intervals."""
    assert get_policy_limits(" Manager ") == {"laptop": 24, "monitor": 36}


def test_unknown_role_returns_unknown_role():
    """An intern is not a role in the policy, so the lookup returns unknown_role."""
    assert get_policy_limits("intern") == {"error": "unknown_role"}


def test_missing_employee_cannot_be_checked_for_eligibility():
    """E9999 is not on file, so eligibility returns unknown_employee."""
    assert check_request_eligibility("E9999", "laptop") == {"error": "unknown_employee"}


def test_unknown_employee_is_reported_before_an_unknown_item():
    """Rule 1 comes before rule 2: an unknown employee asking for a tablet is unknown_employee."""
    assert check_request_eligibility("E9999", "drawing tablet") == {"error": "unknown_employee"}


def test_drawing_tablet_is_undetermined():
    """A drawing tablet is not in the policy, so the verdict is undetermined."""
    assert check_request_eligibility("E1004", "drawing tablet") == {
        "verdict": "undetermined",
        "reason": "item_not_in_policy",
    }


def test_pumpkin_spice_is_undetermined_for_the_ceo():
    """Pumpkin spice is not a laptop or a monitor, even for the CEO."""
    assert check_request_eligibility("E1005", "pumpkin spice") == {
        "verdict": "undetermined",
        "reason": "item_not_in_policy",
    }


def test_a_misspelled_monitor_uses_the_monitor_rule():
    """Moniter is a close misspelling, so E1002's monitor from 2023-11-01 (35 months) is ineligible."""
    assert check_request_eligibility("E1002", "moniter", as_of=AS_OF) == {"verdict": "ineligible"}


def test_a_plural_or_capitalized_item_uses_that_item():
    """Monitors and Laptop use the monitor and laptop rules."""
    assert check_request_eligibility("E1001", "Monitors", as_of=AS_OF) == {"verdict": "eligible"}
    assert check_request_eligibility("E1003", " Laptop ", as_of=AS_OF) == {"verdict": "eligible"}


def test_first_monitor_is_eligible():
    """E1001 has no monitor on file, so a monitor request is eligible."""
    assert check_request_eligibility("E1001", "monitor", as_of=AS_OF) == {"verdict": "eligible"}


def test_laptop_older_than_36_months_is_eligible():
    """E1003's laptop from 2022-08-01 is 50 months old on 2026-10-02, so it is eligible."""
    assert check_request_eligibility("E1003", "laptop", as_of=AS_OF) == {"verdict": "eligible"}


def test_engineer_laptop_at_exactly_36_months_is_eligible():
    """A laptop issued 2023-10-02 is exactly 36 whole months old on 2026-10-02."""
    catalog = _engineer_with_laptop(date(2023, 10, 2))
    assert check_request_eligibility("E2000", "laptop", catalog, AS_OF) == {"verdict": "eligible"}


def test_engineer_laptop_one_day_short_of_36_months_is_ineligible():
    """A laptop issued 2023-10-03 is 35 whole months old on 2026-10-02."""
    catalog = _engineer_with_laptop(date(2023, 10, 3))
    assert check_request_eligibility("E2000", "laptop", catalog, AS_OF) == {"verdict": "ineligible"}


def test_a_month_counts_once_the_same_day_is_reached():
    """Whole months count only when the day of the month has been reached."""
    assert _whole_months(date(2026, 1, 31), date(2026, 2, 28)) == 0
    assert _whole_months(date(2026, 1, 31), date(2026, 3, 31)) == 2
    assert _whole_months(date(2026, 1, 15), date(2026, 2, 15)) == 1


def test_manager_laptop_from_june_2025_is_ineligible():
    """E1002's laptop from 2025-06-15 is 15 months old on 2026-10-02, inside 24 months."""
    assert check_request_eligibility("E1002", "laptop", as_of=AS_OF) == {"verdict": "ineligible"}


def test_manager_laptop_is_eligible_after_24_months():
    """E1002's laptop from 2025-06-15 is eligible on 2027-06-15."""
    assert check_request_eligibility("E1002", "laptop", as_of=date(2027, 6, 15)) == {
        "verdict": "eligible"
    }


def test_ceo_laptop_is_eligible_after_a_new_model_launched():
    """E1005's laptop from 2025-01-10 is 20 months old and the current model launched 2026-03-01."""
    assert check_request_eligibility("E1005", "laptop", as_of=AS_OF) == {"verdict": "eligible"}


def test_ceo_laptop_is_ineligible_before_12_months():
    """On 2026-01-09 E1005's laptop is 11 months old, so it is ineligible."""
    assert check_request_eligibility("E1005", "laptop", as_of=date(2026, 1, 9)) == {
        "verdict": "ineligible"
    }


def test_ceo_monitor_is_ineligible_when_no_newer_model_has_launched():
    """E1005's monitor is ineligible because the current monitor launched before the one on file."""
    assert check_request_eligibility("E1005", "monitor", as_of=AS_OF) == {"verdict": "ineligible"}


def test_ceo_item_issued_on_the_launch_date_is_ineligible():
    """A model that launched on the issue date is not newer than the one on file."""
    catalog = MemoryCatalog(
        employees={
            "E3000": {
                "role": Role.ceo,
                "started": date(2018, 1, 1),
                "issued": {Item.laptop: date(2025, 1, 1)},
            }
        },
        launched={Item.laptop: date(2025, 1, 1), Item.monitor: date(2025, 1, 1)},
    )
    assert check_request_eligibility("E3000", "laptop", catalog, AS_OF) == {"verdict": "ineligible"}


def test_eligibility_returns_unknown_role_for_a_role_without_a_policy():
    """An employee whose role has no policy returns unknown_role."""
    catalog = MemoryCatalog(
        employees={
            "E4000": {
                "role": "intern",
                "started": date(2025, 1, 1),
                "issued": {Item.laptop: date(2025, 1, 1)},
            }
        }
    )
    assert check_request_eligibility("E4000", "laptop", catalog, AS_OF) == {"error": "unknown_role"}


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


def test_blank_employee_id_or_request_does_not_write(tmp_path):
    """A review flag with a blank employee id or a blank request returns an error and writes nothing."""
    path = tmp_path / "review_queue.json"
    queue = JsonFileQueue(path)
    assert flag_for_human_review(" ", "stolen laptop", "theft", queue) == {
        "error": "empty_employee_id"
    }
    assert flag_for_human_review("E1003", "", "theft", queue) == {"error": "empty_request"}
    assert not path.exists()


def test_the_decision_date_is_today_by_default(monkeypatch):
    """With no override, the decision date is the day the program runs."""
    monkeypatch.delenv("CLAIMS_AS_OF", raising=False)
    assert as_of() == date.today()


def test_a_bad_decision_date_names_the_setting(monkeypatch):
    """CLAIMS_AS_OF that is not a date raises an error that names the setting and the format."""
    monkeypatch.setenv("CLAIMS_AS_OF", "yesterday")
    with pytest.raises(ValueError, match="CLAIMS_AS_OF must be a date like 2026-10-02"):
        check_request_eligibility("E1001", "monitor")


def test_review_flag_uses_the_configured_queue(tmp_path, monkeypatch):
    """CLAIMS_REVIEW_QUEUE chooses where the default queue writes."""
    path = tmp_path / "queue.json"
    monkeypatch.setenv("CLAIMS_REVIEW_QUEUE", str(path))
    flag_for_human_review("E1004", "E1004 needs a drawing tablet.", "item_not_in_policy")
    assert JsonFileQueue(path)._read()[0]["employee_id"] == "E1004"

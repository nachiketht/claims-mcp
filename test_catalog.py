from datetime import date

import pytest

from catalog import MemoryCatalog
from enums import Item, Role


def test_known_employee_returns_the_record():
    """E1001 is an engineer who started on 2022-07-01 and has a laptop issued on 2022-08-01."""
    record = MemoryCatalog().employee("E1001")
    assert record == {
        "role": Role.engineer,
        "started": date(2022, 7, 1),
        "issued": {Item.laptop: date(2022, 8, 1)},
    }


def test_unknown_employee_returns_nothing():
    """An employee id that is not on file returns nothing."""
    assert MemoryCatalog().employee("E9999") is None


def test_known_role_returns_the_intervals():
    """An engineer may refresh a laptop or a monitor every 36 months."""
    assert MemoryCatalog().policy(Role.engineer) == {Item.laptop: 36, Item.monitor: 36}


def test_unknown_role_returns_nothing():
    """A role that is not in the policy returns nothing."""
    assert MemoryCatalog().policy("intern") is None


def test_catalog_rejects_an_employee_with_no_start_date():
    """An employee record with no start date is rejected by name."""
    with pytest.raises(ValueError, match="E9"):
        MemoryCatalog(employees={"E9": {"role": Role.engineer, "issued": {}}})


def test_catalog_rejects_a_non_positive_interval():
    """A role interval that is not a positive number is rejected by name."""
    with pytest.raises(ValueError, match="engineer laptop"):
        MemoryCatalog(policy={Role.engineer: {Item.laptop: 0, Item.monitor: 36}})

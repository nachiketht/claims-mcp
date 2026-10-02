import os
from datetime import date

from enums import Item, Role


def as_of() -> date:
    """The decision date: CLAIMS_AS_OF (YYYY-MM-DD) when set, otherwise today."""
    fixed = os.environ.get("CLAIMS_AS_OF")
    return date.fromisoformat(fixed) if fixed else date.today()


LAUNCHED = {
    Item.laptop: date(2026, 3, 1),
    Item.monitor: date(2025, 6, 1),
}

EMPLOYEES = {
    "E1001": {
        "role": Role.engineer,
        "started": date(2022, 7, 1),
        "issued": {Item.laptop: date(2022, 8, 1)},
    },
    "E1002": {
        "role": Role.manager,
        "started": date(2023, 8, 1),
        "issued": {Item.laptop: date(2025, 6, 15), Item.monitor: date(2023, 11, 1)},
    },
    "E1003": {
        "role": Role.engineer,
        "started": date(2021, 1, 15),
        "issued": {Item.laptop: date(2022, 8, 1)},
    },
    "E1004": {
        "role": Role.engineer,
        "started": date(2024, 1, 1),
        "issued": {Item.laptop: date(2024, 2, 1)},
    },
    "E1005": {
        "role": Role.ceo,
        "started": date(2018, 1, 15),
        "issued": {Item.laptop: date(2025, 1, 10), Item.monitor: date(2025, 8, 1)},
    },
}

POLICY = {
    Role.engineer: {Item.laptop: 36, Item.monitor: 36},
    Role.manager: {Item.laptop: 24, Item.monitor: 36},
    Role.ceo: {Item.laptop: 12, Item.monitor: 12},
}

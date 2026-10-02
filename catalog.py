from data import EMPLOYEES, LAUNCHED, POLICY
from enums import Item


class Catalog:
    def employee(self, employee_id: str) -> dict | None:
        raise NotImplementedError

    def policy(self, role: str) -> dict | None:
        raise NotImplementedError


class MemoryCatalog(Catalog):
    def __init__(self, employees=None, policy=None, launched=None):
        employees = EMPLOYEES if employees is None else employees
        policy = POLICY if policy is None else policy
        launched = LAUNCHED if launched is None else launched
        for employee_id, record in employees.items():
            if record.get("started") is None:
                raise ValueError(f"employee {employee_id} has no start date")
        for role, intervals in policy.items():
            for item in Item:
                interval = intervals.get(item)
                if type(interval) is not int or interval <= 0:
                    raise ValueError(f"{role} {item} interval is not a positive number")
        self._employees = employees
        self._policy = policy
        self.launched = dict(launched)

    def employee(self, employee_id: str) -> dict | None:
        record = self._employees.get(employee_id)
        if record is None:
            return None
        return {
            "role": record["role"],
            "started": record["started"],
            "issued": dict(record["issued"]),
        }

    def policy(self, role: str) -> dict | None:
        intervals = self._policy.get(role)
        if intervals is None:
            return None
        return dict(intervals)

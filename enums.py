from enum import StrEnum


class Role(StrEnum):
    engineer = "engineer"
    manager = "manager"
    ceo = "ceo"


class Item(StrEnum):
    laptop = "laptop"
    monitor = "monitor"


class Verdict(StrEnum):
    eligible = "eligible"
    ineligible = "ineligible"
    undetermined = "undetermined"


class ToolName(StrEnum):
    get_employee_info = "get_employee_info"
    get_policy_limits = "get_policy_limits"
    check_request_eligibility = "check_request_eligibility"
    flag_for_human_review = "flag_for_human_review"

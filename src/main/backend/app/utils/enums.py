from enum import Enum


class ProjectStatus(str, Enum):
    not_started = "not_started"
    active = "active"
    on_hold = "on_hold"
    complete = "complete"
    abandoned = "abandoned"


class SolutionStatus(str, Enum):
    not_started = "not_started"
    active = "active"
    on_hold = "on_hold"
    complete = "complete"
    abandoned = "abandoned"


class SubcomponentStatus(str, Enum):
    to_do = "to_do"
    in_progress = "in_progress"
    on_hold = "on_hold"
    complete = "complete"
    abandoned = "abandoned"


class RagStatus(str, Enum):
    red = "red"
    amber = "amber"
    green = "green"


class DeliverableType(str, Enum):
    model = "model"
    dashboard = "dashboard"
    dataset = "dataset"
    pipeline = "pipeline"
    automation = "automation"
    policy_process = "policy_process"
    analysis = "analysis"
    other = "other"


class ImpactType(str, Enum):
    revenue = "revenue"
    cost_save = "cost_save"
    risk_reduction = "risk_reduction"
    regulatory = "regulatory"
    enablement = "enablement"
    other = "other"


class ConfidenceLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

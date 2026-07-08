from typing import Literal, Optional

from pydantic import BaseModel, Field


class WorkAllocationTeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)


class WorkAllocationTeamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)


class WorkAllocationTeamRead(BaseModel):
    id: str
    name: str


class WorkAllocationPersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    team_id: Optional[str] = None
    capacity_fte_months: float = 1.0


class WorkAllocationPersonUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    team_id: Optional[str] = None
    capacity_fte_months: Optional[float] = None
    active: Optional[bool] = None


class WorkAllocationPersonRead(BaseModel):
    id: str
    name: str
    team_id: Optional[str] = None
    capacity_fte_months: float
    active: bool


class WorkAllocationTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    fte_months: float = 0.25


class WorkAllocationTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    fte_months: Optional[float] = None


class WorkAllocationTaskRead(BaseModel):
    id: str
    title: str
    fte_months: float
    status: Literal["backlog", "assigned"]


class WorkAllocationProjectRead(BaseModel):
    id: str
    title: str
    status: str
    fte_months: float
    allocated_solution_fte_months: float = 0.0
    residual_fte_months: float = 0.0
    solution_count: int = 0


class WorkAllocationSolutionRead(BaseModel):
    id: str
    project_id: str
    title: str
    version: str
    status: str
    fte_months: float
    allocated_fte_months: float = 0.0
    remaining_fte_months: float = 0.0


class WorkAllocationAssignmentCreate(BaseModel):
    work_item_type: Literal["project", "solution", "task"] = "task"
    work_item_id: Optional[str] = Field(default=None, min_length=1)
    task_id: Optional[str] = Field(default=None, min_length=1)
    assignee_type: Literal["person", "team"]
    assignee_id: str = Field(min_length=1)
    month: str = Field(min_length=7, max_length=7)
    fte_months_allocated: Optional[float] = None


class WorkAllocationAssignmentUpdate(BaseModel):
    assignee_type: Literal["person", "team"]
    assignee_id: str = Field(min_length=1)
    fte_months_allocated: Optional[float] = None


class WorkAllocationAssignmentRead(BaseModel):
    id: str
    work_item_type: Literal["project", "solution", "task"]
    work_item_id: str
    task_id: Optional[str] = None
    assignee_type: Literal["person", "team"]
    assignee_id: str
    assignee_name: Optional[str] = None
    month: str
    fte_months_allocated: float


class WorkAllocationBoardRead(BaseModel):
    projects: list[WorkAllocationProjectRead]
    solutions: list[WorkAllocationSolutionRead]
    teams: list[WorkAllocationTeamRead]
    people: list[WorkAllocationPersonRead]
    allocations: list[WorkAllocationAssignmentRead]

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


class WorkAllocationAssignmentCreate(BaseModel):
    task_id: str = Field(min_length=1)
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
    task_id: str
    assignee_type: Literal["person", "team"]
    assignee_id: str
    assignee_name: Optional[str] = None
    month: str
    fte_months_allocated: float


class WorkAllocationBoardRead(BaseModel):
    tasks: list[WorkAllocationTaskRead]
    teams: list[WorkAllocationTeamRead]
    people: list[WorkAllocationPersonRead]
    allocations: list[WorkAllocationAssignmentRead]

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field


Name180 = Annotated[str, Field(min_length=1, max_length=180)]
OptionalName180 = Annotated[Optional[str], Field(min_length=1, max_length=180)]
Title240 = Annotated[str, Field(min_length=1, max_length=240)]
OptionalTitle240 = Annotated[Optional[str], Field(min_length=1, max_length=240)]
RequiredId = Annotated[str, Field(min_length=1)]
MonthToken = Annotated[str, Field(min_length=7, max_length=7)]


class WorkAllocationTeamCreate(BaseModel):
    name: Name180


class WorkAllocationTeamUpdate(BaseModel):
    name: OptionalName180 = None


class WorkAllocationTeamRead(BaseModel):
    id: str
    name: str


class WorkAllocationPersonCreate(BaseModel):
    name: Name180
    team_id: Optional[str] = None
    capacity_fte_months: float = 1.0


class WorkAllocationPersonUpdate(BaseModel):
    name: OptionalName180 = None
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
    title: Title240
    fte_months: float = 0.25


class WorkAllocationTaskUpdate(BaseModel):
    title: OptionalTitle240 = None
    fte_months: Optional[float] = None


class WorkAllocationTaskRead(BaseModel):
    id: str
    title: str
    fte_months: float
    status: Literal["backlog", "assigned"]


class WorkAllocationAssignmentCreate(BaseModel):
    task_id: RequiredId
    assignee_type: Literal["person", "team"]
    assignee_id: RequiredId
    month: MonthToken
    fte_months_allocated: Optional[float] = None


class WorkAllocationAssignmentUpdate(BaseModel):
    assignee_type: Literal["person", "team"]
    assignee_id: RequiredId
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

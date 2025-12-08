from pydantic import BaseModel, Field
from typing import List, Optional

# Shared Models
class SubTask(BaseModel):
    summary: str = Field(..., max_length=255)
    description: str = Field(..., max_length=1000)
    issueType: str = Field(..., pattern=r'^(Task|Story|Bug)$')
    priority: str = Field(..., pattern=r'^(None|Low|Medium|High)$')
    startDate: Optional[str] = None  # "YYYY-MM-DD HH:mm:ss" or None
    dueDate: Optional[str] = None
    originalEstimate: str = Field(..., max_length=45)  # HH:mm format
    storyPoint: int = Field(..., ge=0, le=2147483647)


class Task(BaseModel):
    summary: str = Field(..., max_length=255)
    description: str = Field(..., max_length=1000)
    issueType: str = Field(..., pattern=r'^(Task|Story|Bug)$')
    priority: str = Field(..., pattern=r'^(None|Low|Medium|High)$')
    startDate: Optional[str] = None
    dueDate: Optional[str] = None
    originalEstimate: str = Field(..., max_length=45)  # HH:mm format
    storyPoint: int = Field(..., ge=0, le=2147483647)
    subTasks: List[SubTask] = Field(default_factory=list)

# Scrum Models
class Sprint(BaseModel):
    name: str = Field(..., max_length=45)
    description: str = Field(..., max_length=1000)
    startDate: Optional[str] = None  # "YYYY-MM-DD" or None
    endDate: Optional[str] = None
    tasks: List[Task]


class ScrumProject(BaseModel):
    project_name: str
    sprints: List[Sprint]

# Kanban Models
class Release(BaseModel):
    version: str = Field(..., max_length=50, pattern=r'^[A-Za-z0-9 .-]+$')
    description: str = Field(..., max_length=1000)
    startDate: Optional[str] = None  # "YYYY-MM-DD" or None
    releaseDate: Optional[str] = None
    tasks: List[Task]


class KanbanProject(BaseModel):
    project_name: str
    releases: List[Release]

# Task-Only Model
class Project(BaseModel):
    project_name: str
    tasks: List[Task]
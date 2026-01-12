from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from app.models.task import TaskStatus, TaskPriority

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    parent_task_id: Optional[int] = None

class TaskCreate(TaskBase):
    assignee_ids: List[int] = []
    tag_names: List[str] = []
    dependency_ids: List[int] = []

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[datetime] = None
    assignee_ids: Optional[List[int]] = None
    tag_names: Optional[List[str]] = None

class TaskBulkUpdate(BaseModel):
    task_ids: List[int]
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee_ids: Optional[List[int]] = None

class AssigneeResponse(BaseModel):
    id: int
    username: str
    email: str
    
    class Config:
        from_attributes = True

class TagResponse(BaseModel):
    id: int
    name: str
    
    class Config:
        from_attributes = True

class TaskResponse(TaskBase):
    id: int
    creator_id: int
    created_at: datetime
    updated_at: datetime
    assignees: List[AssigneeResponse] = []
    tags: List[TagResponse] = []
    subtask_count: int = 0
    is_blocked: bool = False
    
    class Config:
        from_attributes = True

class TaskDetailResponse(TaskResponse):
    subtasks: List['TaskResponse'] = []
    dependencies: List[int] = []
    blocked_by_tasks: List[int] = []

class TaskFilterRequest(BaseModel):
    status: Optional[List[TaskStatus]] = None
    priority: Optional[List[TaskPriority]] = None
    assignee_ids: Optional[List[int]] = None
    tags: Optional[List[str]] = None
    due_date_from: Optional[datetime] = None
    due_date_to: Optional[datetime] = None
    created_after: Optional[datetime] = None
    logic: str = "AND"  # "AND" or "OR"
    
class AnalyticsResponse(BaseModel):
    total_tasks: int
    tasks_by_status: dict
    tasks_by_priority: dict
    overdue_tasks: int
    user_task_distribution: List[dict]
    
class TaskHistoryResponse(BaseModel):
    id: int
    task_id: int
    task_title: str
    user_id: int
    username: str
    field_changed: str
    old_value: Optional[str]
    new_value: Optional[str]
    changed_at: datetime
    
    class Config:
        from_attributes = True
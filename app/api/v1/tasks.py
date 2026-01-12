from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.base import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.task import Task
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskDetailResponse,
    TaskFilterRequest, TaskBulkUpdate, AnalyticsResponse, TaskHistoryResponse
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TaskService(db)
    task = service.create_task(task_data, current_user.id)
    return task

@router.get("/{task_id}", response_model=TaskDetailResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TaskService(db)
    task = service.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return task

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TaskService(db)
    task = service.update_task(task_id, task_data, current_user.id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return task

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    db.delete(task)
    db.commit()
    
    # Invalidate cache
    service = TaskService(db)
    service._invalidate_task_cache()

@router.post("/bulk-update")
def bulk_update_tasks(
    bulk_data: TaskBulkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TaskService(db)
    updated_count = service.bulk_update_tasks(bulk_data, current_user.id)
    
    return {
        "message": f"Successfully updated {updated_count} tasks",
        "updated_count": updated_count
    }

@router.post("/filter", response_model=List[TaskResponse])
def filter_tasks(
    filters: TaskFilterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TaskService(db)
    tasks = service.filter_tasks(filters, current_user.id)
    return tasks

@router.get("/analytics/dashboard", response_model=AnalyticsResponse)
def get_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    service = TaskService(db)
    analytics = service.get_analytics()
    return analytics

@router.get("/timeline/me", response_model=List[TaskHistoryResponse])
def get_my_timeline(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TaskService(db)
    history = service.get_user_timeline(current_user.id, days)
    return history

@router.post("/{task_id}/dependencies/{depends_on_task_id}", status_code=status.HTTP_201_CREATED)
def add_task_dependency(
    task_id: int,
    depends_on_task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.task import TaskDependency
    
    # Check both tasks exist
    task = db.query(Task).filter(Task.id == task_id).first()
    depends_on = db.query(Task).filter(Task.id == depends_on_task_id).first()
    
    if not task or not depends_on:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both tasks not found"
        )
    
    # Check if dependency already exists
    existing = db.query(TaskDependency).filter(
        TaskDependency.task_id == task_id,
        TaskDependency.depends_on_task_id == depends_on_task_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dependency already exists"
        )
    
    # Create dependency
    dependency = TaskDependency(
        task_id=task_id,
        depends_on_task_id=depends_on_task_id
    )
    db.add(dependency)
    db.commit()
    
    return {"message": "Dependency added successfully"}

@router.delete("/{task_id}/dependencies/{depends_on_task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_task_dependency(
    task_id: int,
    depends_on_task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.task import TaskDependency
    
    dependency = db.query(TaskDependency).filter(
        TaskDependency.task_id == task_id,
        TaskDependency.depends_on_task_id == depends_on_task_id
    ).first()
    
    if not dependency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found"
        )
    
    db.delete(dependency)
    db.commit()
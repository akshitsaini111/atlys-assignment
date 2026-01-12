from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.task import Task, TaskAssignment, TaskDependency, Tag, TaskHistory, TaskStatus, TaskPriority
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate, TaskFilterRequest, TaskBulkUpdate
from app.db.redis_client import get_redis
import json

class TaskService:
    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
    
    def create_task(self, task_data: TaskCreate, creator_id: int) -> Task:
        # Create task
        task = Task(
            title=task_data.title,
            description=task_data.description,
            status=task_data.status,
            priority=task_data.priority,
            due_date=task_data.due_date,
            creator_id=creator_id,
            parent_task_id=task_data.parent_task_id
        )
        self.db.add(task)
        self.db.flush()
        
        # Add assignees
        for assignee_id in task_data.assignee_ids:
            assignment = TaskAssignment(task_id=task.id, user_id=assignee_id)
            self.db.add(assignment)
        
        # Add tags
        for tag_name in task_data.tag_names:
            tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                self.db.add(tag)
            task.tags.append(tag)
        
        # Add dependencies
        for dep_id in task_data.dependency_ids:
            dependency = TaskDependency(task_id=task.id, depends_on_task_id=dep_id)
            self.db.add(dependency)
        
        self.db.commit()
        self.db.refresh(task)
        
        # Invalidate cache
        self._invalidate_task_cache()
        
        return task
    
    def get_task(self, task_id: int) -> Optional[Task]:
        # Try cache first
        cache_key = f"task:{task_id}"
        cached = self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        task = (
            self.db.query(Task)
            .options(
                joinedload(Task.assignees).joinedload(TaskAssignment.assignee),
                joinedload(Task.tags),
                joinedload(Task.subtasks),
                joinedload(Task.dependencies),
                joinedload(Task.blocked_by)
            )
            .filter(Task.id == task_id)
            .first()
        )
        
        if task:
            # Cache for 5 minutes
            self.redis.setex(cache_key, 300, json.dumps(task, default=str))
        
        return task
    
    def update_task(self, task_id: int, task_data: TaskUpdate, user_id: int) -> Optional[Task]:
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return None
        
        # Track changes for history
        changes = []
        
        for field, value in task_data.dict(exclude_unset=True).items():
            if field == "assignee_ids" and value is not None:
                # Update assignees
                self.db.query(TaskAssignment).filter(TaskAssignment.task_id == task_id).delete()
                for assignee_id in value:
                    assignment = TaskAssignment(task_id=task_id, user_id=assignee_id)
                    self.db.add(assignment)
            elif field == "tag_names" and value is not None:
                # Update tags
                task.tags.clear()
                for tag_name in value:
                    tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        self.db.add(tag)
                    task.tags.append(tag)
            else:
                old_value = getattr(task, field)
                if old_value != value:
                    changes.append((field, str(old_value), str(value)))
                    setattr(task, field, value)
        
        # Record history
        for field, old_val, new_val in changes:
            history = TaskHistory(
                task_id=task_id,
                user_id=user_id,
                field_changed=field,
                old_value=old_val,
                new_value=new_val
            )
            self.db.add(history)
        
        self.db.commit()
        self.db.refresh(task)
        
        # Invalidate cache
        self._invalidate_task_cache()
        self.redis.delete(f"task:{task_id}")
        
        return task
    
    def bulk_update_tasks(self, bulk_data: TaskBulkUpdate, user_id: int) -> int:
        tasks = self.db.query(Task).filter(Task.id.in_(bulk_data.task_ids)).all()
        
        updated_count = 0
        for task in tasks:
            changes = []
            
            if bulk_data.status is not None and task.status != bulk_data.status:
                changes.append(("status", str(task.status), str(bulk_data.status)))
                task.status = bulk_data.status
            
            if bulk_data.priority is not None and task.priority != bulk_data.priority:
                changes.append(("priority", str(task.priority), str(bulk_data.priority)))
                task.priority = bulk_data.priority
            
            if bulk_data.assignee_ids is not None:
                self.db.query(TaskAssignment).filter(TaskAssignment.task_id == task.id).delete()
                for assignee_id in bulk_data.assignee_ids:
                    assignment = TaskAssignment(task_id=task.id, user_id=assignee_id)
                    self.db.add(assignment)
                changes.append(("assignees", "", ",".join(map(str, bulk_data.assignee_ids))))
            
            # Record history
            for field, old_val, new_val in changes:
                history = TaskHistory(
                    task_id=task.id,
                    user_id=user_id,
                    field_changed=field,
                    old_value=old_val,
                    new_value=new_val
                )
                self.db.add(history)
            
            if changes:
                updated_count += 1
        
        self.db.commit()
        self._invalidate_task_cache()
        
        return updated_count
    
    def filter_tasks(self, filters: TaskFilterRequest, user_id: int) -> List[Task]:
        query = self.db.query(Task).options(
            joinedload(Task.assignees).joinedload(TaskAssignment.assignee),
            joinedload(Task.tags)
        )
        
        conditions = []
        
        if filters.status:
            conditions.append(Task.status.in_(filters.status))
        
        if filters.priority:
            conditions.append(Task.priority.in_(filters.priority))
        
        if filters.assignee_ids:
            query = query.join(TaskAssignment).filter(TaskAssignment.user_id.in_(filters.assignee_ids))
        
        if filters.tags:
            query = query.join(Task.tags).filter(Tag.name.in_(filters.tags))
        
        if filters.due_date_from:
            conditions.append(Task.due_date >= filters.due_date_from)
        
        if filters.due_date_to:
            conditions.append(Task.due_date <= filters.due_date_to)
        
        if filters.created_after:
            conditions.append(Task.created_at >= filters.created_after)
        
        if conditions:
            if filters.logic == "AND":
                query = query.filter(and_(*conditions))
            else:
                query = query.filter(or_(*conditions))
        
        return query.distinct().all()
    
    def get_analytics(self) -> dict:
        # Try cache first
        cache_key = "analytics:dashboard"
        cached = self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        total_tasks = self.db.query(func.count(Task.id)).scalar()
        
        # Tasks by status
        status_counts = (
            self.db.query(Task.status, func.count(Task.id))
            .group_by(Task.status)
            .all()
        )
        tasks_by_status = {str(status): count for status, count in status_counts}
        
        # Tasks by priority
        priority_counts = (
            self.db.query(Task.priority, func.count(Task.id))
            .group_by(Task.priority)
            .all()
        )
        tasks_by_priority = {str(priority): count for priority, count in priority_counts}
        
        # Overdue tasks
        overdue = (
            self.db.query(func.count(Task.id))
            .filter(Task.due_date < datetime.utcnow(), Task.status != TaskStatus.DONE)
            .scalar()
        )
        
        # User task distribution
        user_distribution = (
            self.db.query(
                User.username,
                User.email,
                func.count(TaskAssignment.id).label("task_count"),
                func.count(
                    func.case(
                        (and_(Task.due_date < datetime.utcnow(), Task.status != TaskStatus.DONE), 1)
                    )
                ).label("overdue_count")
            )
            .join(TaskAssignment, User.id == TaskAssignment.user_id)
            .join(Task, TaskAssignment.task_id == Task.id)
            .group_by(User.id)
            .all()
        )
        
        user_dist_list = [
            {
                "username": username,
                "email": email,
                "total_tasks": task_count,
                "overdue_tasks": overdue_count
            }
            for username, email, task_count, overdue_count in user_distribution
        ]
        
        result = {
            "total_tasks": total_tasks,
            "tasks_by_status": tasks_by_status,
            "tasks_by_priority": tasks_by_priority,
            "overdue_tasks": overdue,
            "user_task_distribution": user_dist_list
        }
        
        # Cache for 2 minutes
        self.redis.setex(cache_key, 120, json.dumps(result))
        
        return result
    
    def get_user_timeline(self, user_id: int, days: int = 7) -> List[TaskHistory]:
        from_date = datetime.utcnow() - timedelta(days=days)
        
        # Get tasks assigned to user
        user_task_ids = (
            self.db.query(TaskAssignment.task_id)
            .filter(TaskAssignment.user_id == user_id)
            .subquery()
        )
        
        history = (
            self.db.query(TaskHistory)
            .join(Task, TaskHistory.task_id == Task.id)
            .join(User, TaskHistory.user_id == User.id)
            .filter(
                TaskHistory.task_id.in_(user_task_ids),
                TaskHistory.changed_at >= from_date
            )
            .order_by(TaskHistory.changed_at.desc())
            .all()
        )
        
        return history
    
    def _invalidate_task_cache(self):
        """Invalidate all task-related caches"""
        self.redis.delete("analytics:dashboard")
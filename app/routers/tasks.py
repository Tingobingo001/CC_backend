from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from  ..import models, schemas
from  ..database import get_db
from ..auth import require_role

router = APIRouter(prefix="/teams/{team_id}/projects/{project_id}/tasks",tags=["tasks"])

ALL_ROLES = (models.Role.owner, models.Role.maintainer, models.Role.member, models.Role.viewer)
WRITE_ROLES = (models.Role.owner, models.Role.maintainer, models.Role.member)
MANAGE_ROLES = (models.Role.owner, models.Role.maintainer)

def get_project_or_404(db: Session, team_id: int, project_id: int) -> models.Project:
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.team_id == team_id
    ).first()

    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project

def get_team_or_404(db: Session, project_id: int, task_id: int) -> models.Task:
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.project_id == project_id,
    ).first()

    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task

def parse_enum(enum_cls, value: str, field: str):
    try:
        return enum_cls(value)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail=f"Invalid {field}. Must be on of : {[e.value for e in enum_cls ]}")

def task_to_out(task: models.Task) -> schemas.TaskOut:
    return schemas.TaskOut(
        id=task.id, project_id=task.project_id, title=task.title,
        description=task.description, status=task.status.value,
        created_at=task.created_at,
        assigned_ids = [a.user_id for a in task.assignments]
    )

@router.post("", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
        team_id: int,
        project_id: int,
        task_in: schemas.TaskCreate,
        db: Session = Depends(get_db),
        membership: models.TeamMembership = Depends(require_role(*WRITE_ROLES)),
):
    getproject = get_project_or_404(db, team_id, project_id)
    task_status = parse_enum(models.TaskStatus, task_in.status, "status")
    task_priority = parse_enum(models.TaskPriority, task_in.priority, "priority")

    #every assignee must be a member of this team
    for user_id in task_in.assigned_ids:
        is_member = db.query(models.TeamMember).filter(
            models.TeamMember.team_id == team_id,
            models.TeamMember.user_id == user_id
        ).first()

        if not is_member:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail=f"User {user_id} is not a member of the team")

    task = models.Task(
        project_id=project_id, title = task_in.title,
        description = task_in.description, status = task_status,
        priority = task_priority, created_at = membership.user_id
    )
    db.add(task)
    db.flush()

    return task_to_out(task)

@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(
        team_id: int,
        project_id: int,
        db: Session = Depends(get_db),
        membership: models.TeamMembership = Depends(require_role(*ALL_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
    return [task_to_out(task) for task in tasks]

@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
        team_id: int,
        project_id: int,
        task_id: int,
        db: Session = Depends(get_db),
        membership: models.TeamMembership = Depends(require_role(*ALL_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    return task_to_out(get_team_or_404(db, project_id, task_id))

@router.put("/{task_id}", response_model=schemas.TaskOut)
def update_task(
        team_id: int,
        project_id: int,
        task_id: int,
        task_in: schemas.TaskUpdate,
        db: Session = Depends(get_db),
        membership: models.TeamMembership = Depends(require_role(*WRITE_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    task = get_team_or_404(db, project_id, task_id)

    updates = task_in.model.dump(exclude_unset=True)

    if "status" in updates:
        updates["status"] = parse_enum(models.TaskStatus, updates["status"], "status")
    if "priority" in updates:
        updates["priority"] = parse_enum(models.TaskPriority, updates["priority"], "priority")
    for field, value in updates.items():
        setattr(task, field, value)

    db.add(models.ActivityLog(team_id=team_id, actor_id=membership.user_id, action=f"updated task '{task.title}'"))
    db.commit()
    db.refresh(task)
    return task_to_out(task)

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..auth import require_role

router = APIRouter(prefix="/teams/{team_id}/projects/{project_id}/tasks", tags=["tasks"])

ALL_ROLES = (models.Role.owner, models.Role.maintainer, models.Role.member, models.Role.viewer)
WRITE_ROLES = (models.Role.owner, models.Role.maintainer, models.Role.member)
MANAGE_ROLES = (models.Role.owner, models.Role.maintainer)

"""This router implements the complete task management layer of your application: 
it performs CRUD operations on tasks, enforces role-based permissions, validates projects, 
tasks, and enum values, ensures assignees are valid team members, manages task assignments, 
logs important actions, and returns task data in a consistent API format."""
def get_project_or_404(db: Session, team_id: int, project_id: int) -> models.Project:
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.team_id == team_id,
    ).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def get_task_or_404(db: Session, project_id: int, task_id: int) -> models.Task:
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.project_id == project_id,
    ).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def parse_enum(enum_cls, value: str, field: str):
    try:
        return enum_cls(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {field}. Must be one of: {[e.value for e in enum_cls]}",
        )


def task_to_out(task: models.Task) -> schemas.TaskOut:
    return schemas.TaskOut(
        id=task.id, project_id=task.project_id, title=task.title,
        description=task.description, status=task.status.value,
        priority=task.priority.value, created_by=task.created_by,
        created_at=task.created_at,
        assignee_ids=[a.user_id for a in task.assignments],
    )


@router.post("", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    team_id: int,
    project_id: int,
    task_in: schemas.TaskCreate,
    db: Session = Depends(get_db),
    membership: models.TeamMembership = Depends(require_role(*WRITE_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    task_status = parse_enum(models.TaskStatus, task_in.status, "status")
    task_priority = parse_enum(models.TaskPriority, task_in.priority, "priority")

    # every assignee must be a member of this team
    for user_id in task_in.assignee_ids:
        is_member = db.query(models.TeamMembership).filter(
            models.TeamMembership.team_id == team_id,
            models.TeamMembership.user_id == user_id,
        ).first()
        if not is_member:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"User {user_id} is not a member of this team")

    task = models.Task(
        project_id=project_id, title=task_in.title, description=task_in.description,
        status=task_status, priority=task_priority, created_by=membership.user_id
    )
    db.add(task)
    db.flush()                                        # task.id exists now

    for user_id in set(task_in.assignee_ids):         # set() dedupes
        db.add(models.TaskAssignment(task_id=task.id, user_id=user_id))

    db.add(models.ActivityLog(team_id=team_id, actor_id=membership.user_id,
                              action=f"created task '{task.title}'"))
    db.commit()
    db.refresh(task)
    return task_to_out(task)


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(
    team_id: int,
    project_id: int,
    db: Session = Depends(get_db),
    membership: models.TeamMembership = Depends(require_role(*ALL_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
    return [task_to_out(t) for t in tasks]


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
    team_id: int,
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    membership: models.TeamMembership = Depends(require_role(*ALL_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    return task_to_out(get_task_or_404(db, project_id, task_id))


@router.patch("/{task_id}", response_model=schemas.TaskOut)
def update_task(
    team_id: int,
    project_id: int,
    task_id: int,
    task_in: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    membership: models.TeamMembership = Depends(require_role(*WRITE_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    task = get_task_or_404(db, project_id, task_id)

    updates = task_in.model_dump(exclude_unset=True)
    if "status" in updates:
        updates["status"] = parse_enum(models.TaskStatus, updates["status"], "status")
    if "priority" in updates:
        updates["priority"] = parse_enum(models.TaskPriority, updates["priority"], "priority")
    for field, value in updates.items():
        setattr(task, field, value)

    db.add(models.ActivityLog(team_id=team_id, actor_id=membership.user_id,
                              action=f"updated task '{task.title}'"))
    db.commit()
    db.refresh(task)
    return task_to_out(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    team_id: int,
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    membership: models.TeamMembership = Depends(require_role(*MANAGE_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    task = get_task_or_404(db, project_id, task_id)

    db.query(models.TaskAssignment).filter(models.TaskAssignment.task_id == task_id).delete()
    db.add(models.ActivityLog(team_id=team_id, actor_id=membership.user_id,
                              action=f"deleted task '{task.title}'"))
    db.delete(task)
    db.commit()


@router.post("/{task_id}/assignees/{user_id}", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def assign_user(
    team_id: int,
    project_id: int,
    task_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    membership: models.TeamMembership = Depends(require_role(*WRITE_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    task = get_task_or_404(db, project_id, task_id)

    is_member = db.query(models.TeamMembership).filter(
        models.TeamMembership.team_id == team_id,
        models.TeamMembership.user_id == user_id,
    ).first()
    if not is_member:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="User is not a member of this team")

    existing = db.query(models.TaskAssignment).filter(
        models.TaskAssignment.task_id == task_id,
        models.TaskAssignment.user_id == user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already assigned")

    db.add(models.TaskAssignment(task_id=task_id, user_id=user_id))
    db.commit()
    db.refresh(task)
    return task_to_out(task)


@router.delete("/{task_id}/assignees/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_user(
    team_id: int,
    project_id: int,
    task_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    membership: models.TeamMembership = Depends(require_role(*WRITE_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    get_task_or_404(db, project_id, task_id)

    assignment = db.query(models.TaskAssignment).filter(
        models.TaskAssignment.task_id == task_id,
        models.TaskAssignment.user_id == user_id,
    ).first()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    db.delete(assignment)
    db.commit()

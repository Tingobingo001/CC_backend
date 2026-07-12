
""" It allows team members to add comments to a task and view all comments on a task.
It follows the same structure as your Team, Project, and Task routers.
This router provides the commenting feature for tasks: authenticated team members
can add comments to existing tasks and retrieve all comments on a task,
while the code reuses existing permission and validation helpers to keep
the implementation clean and consistent."""




from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..auth import require_role
from .tasks import get_project_or_404, get_task_or_404, ALL_ROLES

router = APIRouter(prefix="/teams/{team_id}/projects/{project_id}/tasks/{task_id}/comments", tags=["comments"])


@router.post("", response_model=schemas.CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    team_id: int,
    project_id: int,
    task_id: int,
    comment_in: schemas.CommentCreate,
    db: Session = Depends(get_db),
    membership: models.TeamMembership = Depends(require_role(*ALL_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    task = get_task_or_404(db, project_id, task_id)

    comment = models.Comment(task_id=task_id, author_id=membership.user_id, content=comment_in.content)
    db.add(comment)
    db.add(models.ActivityLog(team_id=team_id, actor_id=membership.user_id,
                              action=f"commented on task '{task.title}'"))
    db.commit()
    db.refresh(comment)
    return comment


@router.get("", response_model=list[schemas.CommentOut])
def list_comments(
    team_id: int,
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    membership: models.TeamMembership = Depends(require_role(*ALL_ROLES)),
):
    get_project_or_404(db, team_id, project_id)
    get_task_or_404(db, project_id, task_id)
    return db.query(models.Comment).filter(models.Comment.task_id == task_id).all()


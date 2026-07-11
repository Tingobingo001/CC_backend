from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..import models, schemas
from ..database import get_db
from ..auth import get_current_user, require_role

router = APIRouter(prefix="/teams/{team_id}/projects", tags=["projects"])

ALL_ROLES = (models.Role.owner, models.Role.maintainer, models.Role.member, models.Role.viewer)
MANAGE_ROLES = (models.Role.owner, models.Role.maintainer)


@router.post("", response_model=schemas.ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
        team_id: int,
        project_in: schemas.ProjectCreate,
        db: Session = Depends(get_db),
        membership: models.TeamMembership = Depends(require_role(*MANAGE_ROLES)),
):
    project = models.Project(team_id=team_id, name = project_in.name, description = project_in.description)
    db.add(project)
    db.add(models.ActivityLog(
        team_id=team_id,
        actor_id=membership.user_id,
        action=f"created project '{project.name}'",
    ))
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(
        team_id: int,
        db: Session = Depends(get_db),
        membership: models.TeamMembership = Depends(require_role(*ALL_ROLES))
):
    return db.query(models.Project).filter(models.Project.team_id == team_id).all()


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(
        team_id: int,
        project_id: int,
        db: Session = Depends(get_db),
        membership: models.TeamMembership = Depends(require_role(*ALL_ROLES))
):



    project = db.query(models.Project).filter(models.Project.team_id == team_id, models.Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project

@router.patch("/{project_id}", response_model=schemas.ProjectOut)
def update_project(
        team_id: int,
        project_id: int,
        project_in: schemas.ProjectUpdate,
        db: Session = Depends(get_db),
        membership: models.TeamMembership = Depends(require_role(*MANAGE_ROLES))
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id, models.Project.team_id == team_id,).first()

    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    updates = project_in.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)

    db.add(models.ActivityLog(
        team_id=team_id,
        actor_id=membership.user_id,
        action=f"updated project '{project.name}'",
    ))
    db.commit()
    db.refresh(project)
    return project

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
        team_id: int,
        project_id: int,
        db: Session = Depends(get_db),
        membership: models.TeamMembership = Depends(require_role(*MANAGE_ROLES))
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.team_id == team_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    db.add(models.ActivityLog(
        team_id=team_id,
        actor_id=membership.user_id,
        action=f"deleted project '{project.name}'",
    ))
    db.delete(project)
    db.commit()





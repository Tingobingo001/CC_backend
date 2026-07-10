from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/teams", tags=["teams"])

@router.post("", response_model=schemas.TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
        team_in: schemas.TeamCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    team = models.Team(name=team_in.name)
    db.add(team)
    db.flush()

    membership = models.TeamMembership(
        user_id=current_user.id,
        team_id=team.id,
        role=models.Role.owner
    )

    db.add(membership)

    db.add(models.ActivityLog(
        team_id=team.id,
        actor_id=current_user.id,
        action=f"created team '{team.name}'",
    ))
    db.commit()
    db.refresh(team)
    return team

@router.get("", response_model=list[schemas.TeamOut])
def list_my_teams(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
):
    memberships = db.query(models.TeamMembership).filter(models.TeamMembership.user_id == current_user.id).all()
    return [m.team for m in memberships]

@router.get("/{team_id}/members", response_model = list[schemas.MemberOut])
def list_members(
        team_id: int,
        db: Session= Depends(get_db),
        current_user: models.User = Depends(get_current_user),
):

    #the person asking should be able to view
    my_membership = db.query(models.TeamMembership).filter(models.TeamMembership.team_id == team_id, models.TeamMembership.user_id == current_user.id).first()
    if not my_membership:
        raise HTTPException(status_code=403, detail="You are not a member of this team")

    members = db.query(models.TeamMembership).filter(models.TeamMembership.team_id == team_id).all()
    return [
        schemas.MemberOut(user_id=m.user.id, name=m.user.name, email=m.user.email, role=m.role.value)
        for m in members
    ]





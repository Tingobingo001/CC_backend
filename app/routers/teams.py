from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user, require_role

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


#this func below returns the list of members in a team after verifying requester belong to that team
#key idea : delegates all permission checking to the reusable require_role() dependency instead of doing those checks inside the endpoint.
#Anyone who belongs to the team may view the member list.
@router.get("/{team_id}/members", response_model = list[schemas.MemberOut])
def list_members(
        team_id: int,
        db: Session= Depends(get_db),
        membership: models.TeamMembership = Depends(
            require_role(models.Role.owner, models.Role.maintainer, models.Role.member, models.Role.viewer)),
):

    #the person asking should be able to view
    memberships = db.query(models.TeamMembership).filter(models.TeamMembership.team_id == team_id).all()
    members = db.query(models.TeamMembership).filter(models.TeamMembership.team_id == team_id).all()
    return [
        schemas.MemberOut(user_id=m.user.id, name=m.user.name, email=m.user.email, role=m.role.value)
        for m in members
    ]



"""At a high level, this endpoint adds an existing user to a team.
Its main purpose is:Allow authorized team leaders (Owner or Maintainer) 
to invite another registered user into the team with a specified role."""
@router.post("/{team_id}/members", response_model=schemas.MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
        team_id: int,
        member_in: schemas.MemberAdd,
        db:Session = Depends(get_db),
        membership: models.TeamMembership = Depends(
            require_role(models.Role.owner, models.Role.maintainer)
        ),
):
    user=db.query(models.User).filter(models.User.email == member_in.email).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = db.query(models.TeamMembership).filter(
        models.TeamMembership.team_id == team_id,
        models.TeamMembership.user_id == user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    try:
        role = models.Role(member_in.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role. Must be one of: {[r.value for r in models.Role]}",
        )

    new_membership = models.TeamMembership(
        user_id=user.id,
        team_id=team_id,
        role=role
    )
    db.add(new_membership)
    db.add(models.ActivityLog(
        team_id=team_id,
        actor_id=membership.user_id,
        action=f"added user '{user.email}' as '{member_in.role}'",
    ))

    db.commit()
    return schemas.MemberOut(user_id=user.id, name=user.name, email=user.email, role=member_in.role)

@router.get("/{team_id}/activity", response_model=list[schemas.ActivityOut])
def team_activity(
    team_id: int,
    db: Session = Depends(get_db),
    membership: models.TeamMembership = Depends(require_role(
        models.Role.owner, models.Role.maintainer, models.Role.member, models.Role.viewer
    )),
):
    return db.query(models.ActivityLog).filter(
        models.ActivityLog.team_id == team_id
    ).order_by(models.ActivityLog.created_at.desc()).all()
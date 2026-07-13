from dns.dnssec import algorithm_to_text
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, oauth2
from passlib.handlers.sun_md5_crypt import raw_sun_md5_crypt
from pip._internal.utils import retry
from sqlalchemy.orm import Session, dependency
from .database import get_db
from . import models
from .config import SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain : str, hashed : str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id : int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

#who is making the request is answered by the vlock below

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) :
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_error
    return user

#we create a reusable authorization mechanism based on team role, in essencr ROLE BASED AUTHORIZATION
#auth answer:who is the user, this func answers does the users have perms to perform this action
def require_role(*allowed_roles: models.Role):
    """builds a dependency that admits only given roles"""
    def dependency(
            team_id : int,
            db: Session = Depends(get_db),
            current_user: models.User = Depends(get_current_user),
    ) -> models.TeamMembership:
        membership = db.query(models.TeamMembership).filter(
            models.TeamMembership.team_id == team_id,
            models.TeamMembership.user_id == current_user.id,
        ).first()
        if membership is None:
           raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not in the team")
        if membership.role not in allowed_roles:
           raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role for the action")
        return membership
    return dependency
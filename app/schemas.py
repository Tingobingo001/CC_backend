from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1,max_length=100)
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TeamCreate(BaseModel):
    name : str = Field(min_length=1, max_length=100)

class TeamOut(BaseModel):
    id: int
    name: str
    created_at : datetime

    class Config:
        from_attributes = True

class MemberAdd(BaseModel):
    email: EmailStr
    role: str="member"

class MemberOut(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    role: str

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    description: str | None = None

class ProjectUpdate(BaseModel):
    name: str| None = Field(default=None, min_length = 1, max_length=100)
    description: str | None = None

class ProjectOut(BaseModel):
    id: int
    team_id: int
    name: str
    description: str
    created_at : datetime

    class Config:
        from_attributes = True


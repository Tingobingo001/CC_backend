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

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    status: str = "todo"
    priority: str = "medium"
    assignee_ids: list[int] = []   #multi-assignee input

class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = None
    priority: str | None = None

class TaskOut(BaseModel):
    id: int
    project_id: int
    title: str
    description: str
    status: str
    priority: str
    created_by: int
    created_at: datetime
    assignee_ids: list[int] = []

    class Config:
        from_attributes = True

class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

class CommentOut(BaseModel):
    id: int
    task_id: int
    author_id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class ActivityOut(BaseModel):
    id: int
    team_id: int
    actor_id: int
    action: str
    created_at: datetime

    class Config:
        from_attributes = True
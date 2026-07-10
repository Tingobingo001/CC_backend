from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime,timezone
import enum
from .database import Base

def utcnow():
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    owner = "owner"
    maintainer = "maintainer"
    member = "member"
    viewer = "viewer"

class TaskStatus(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    viewer = "viewer"

class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True,index=True)
    email = Column(String,nullable=False, unique=True, index=True)
    name = Column(String,nullable=False)
    password_hash = Column(String,nullable=False)
    created_at = Column(DateTime,default= utcnow)

    memberships = relationship("TeamMembership",back_populates="user")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True,index=True)
    name = Column(String,nullable=False)
    created_at = Column(DateTime,default= utcnow)

    memberships = relationship("TeamMembership",back_populates="team")
    projects = relationship("Project",back_populates="team")

class TeamMembership(Base):
    __tablename__ = "team_memberships"
    id = Column(Integer, primary_key=True,index=True)
    user_id = Column(Integer,ForeignKey("users.id"), nullable=False)
    team_id = Column(Integer,ForeignKey("teams.id"), nullable=False)
    role = Column(Enum(Role),nullable=False,default = Role.member)
    joined_at = Column(DateTime,default = utcnow)

    user = relationship("User", back_populates="memberships")
    team = relationship("Team", back_populates="memberships")


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True,index=True)
    team_id = Column(Integer,ForeignKey("teams.id"), nullable=False)
    name = Column(String,nullable=False)
    description = Column(Text,default = "")
    created_at = Column(DateTime,default = utcnow)

    team = relationship("Team", back_populates="projects")
    tasks = relationship("Task",back_populates="project")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True,index=True)
    project_id = Column(Integer,ForeignKey("projects.id"), nullable=False)
    title = Column(String,nullable=False)
    description = Column(Text,default = "")
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.todo)
    priority = Column(Enum(TaskPriority), nullable=False, default=TaskPriority.medium)
    created_at = Column(DateTime,default = utcnow)

    project = relationship("Project", back_populates="tasks")
    assignments = relationship("TaskAssignment", back_populates="task")
    comments = relationship("Comment",back_populates="task")

class TaskAssignment(Base):
    """Join table: one task-> many assignees, ones user -> many tasks"""
    __tablename__ = "task_assignments"
    id = Column(Integer, primary_key=True,index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    task = relationship("Task", back_populates="assignments")
    user = relationship("User")

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True,index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text,nullable=False)
    created_at = Column(DateTime,default = utcnow)

    task = relationship("Task", back_populates="comments")
    author = relationship("User")

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True,index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    created_at = Column(DateTime,default = utcnow)


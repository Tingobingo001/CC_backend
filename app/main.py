from fastapi import FastAPI
from sqlalchemy.orm import configure_mappers

from .database import Base, engine

from . import models  # ensures models are registered before create_all
from .routers import users, teams, projects, tasks, comments

Base.metadata.create_all(bind=engine)   # creates tables (our no-Alembic shortcut)
configure_mappers()



app = FastAPI(title="TaskForge API")


app.include_router(users.router)
app.include_router(teams.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(comments.router)

@app.get("/")
def health():
    return {"status": "ok"}


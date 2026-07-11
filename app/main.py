from fastapi import FastAPI
from sqlalchemy.orm import configure_mappers

from .database import Base, engine
from .routers import users, projects
from . import models  # ensures models are registered before create_all
from .routers import users, teams

Base.metadata.create_all(bind=engine)   # creates tables (our no-Alembic shortcut)
configure_mappers()



app = FastAPI(title="TaskForge API")
app.include_router(users.router)

@app.get("/")
def health():
    return {"status": "ok"}

app.include_router(teams.router)
app.include_router(projects.router)


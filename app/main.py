from fastapi import FastAPI
from .database import Base, engine
from .routers import users
from . import models  # ensures models are registered before create_all

Base.metadata.create_all(bind=engine)   # creates tables (our no-Alembic shortcut)

app = FastAPI(title="TaskForge API")
app.include_router(users.router)

@app.get("/")
def health():
    return {"status": "ok"}
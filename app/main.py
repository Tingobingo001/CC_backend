from fastapi import FastAPI
from sqlalchemy.orm import configure_mappers

from .database import Base, engine

from . import models  # ensures models are registered before create_all
from .routers import users, teams, projects, tasks, comments
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

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

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": 422, "message": "Validation failed", "details": exc.errors()}},)
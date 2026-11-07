"""FastAPI application entry point.

The database schema is created by Alembic: run ``poetry run alembic upgrade head``
before starting the server (see README.md).
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.auth import router as auth_router
from app.api.groups import router as groups_router
from app.api.quick_split import router as quick_split_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="SplitEasy", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(quick_split_router)
app.include_router(auth_router)
app.include_router(groups_router)

templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")

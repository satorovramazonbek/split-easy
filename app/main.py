"""FastAPI application entry point.

The database schema is created by Alembic: run ``poetry run alembic upgrade head``
before starting the server (see README.md).
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.dependencies import NotificationServiceDep
from app.api.expenses import router as expenses_router
from app.api.groups import router as groups_router
from app.api.notifications import router as notifications_router
from app.api.quick_split import router as quick_split_router
from app.api.quick_split_draft import router as quick_split_draft_router
from app.api.reports import router as reports_router
from app.services.group_service import GroupNotFoundError, GroupPermissionError
from app.web.pages import (
    LoginRequiredError,
    OptionalUser,
    group_error_handler,
    login_required_handler,
)
from app.web.pages import router as pages_router
from app.web.templating import templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="SplitEasy", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(quick_split_router)
app.include_router(auth_router)
app.include_router(groups_router)
app.include_router(expenses_router)
app.include_router(notifications_router)
app.include_router(quick_split_draft_router)
app.include_router(reports_router)
app.include_router(pages_router)

# HTML pages only: the JSON API catches these errors itself and returns JSON.
app.add_exception_handler(LoginRequiredError, login_required_handler)
app.add_exception_handler(GroupNotFoundError, group_error_handler)
app.add_exception_handler(GroupPermissionError, group_error_handler)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(
    request: Request, user: OptionalUser, notifications: NotificationServiceDep
) -> HTMLResponse:
    # Guests: the quick split works in browser memory only (nothing is saved).
    # Signed-in users: the page loads and saves its state via /api/quick-split/draft.
    if user is not None:
        request.state.unread = notifications.unread_count(user)
    return templates.TemplateResponse(request, "index.html", {"user": user})

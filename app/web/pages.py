"""All HTML page routers in one place (Jinja2 + Bootstrap).

The pages are split by topic so each module has one job (SRP):
- ``auth_pages`` - login, registration, logout;
- ``group_pages`` - my groups, the group page, members;
- ``expense_pages`` - expenses, settlements, export;
- ``notification_pages`` - notifications;
- ``common`` - rendering, redirects, the login cookie, error handlers.
"""

from fastapi import APIRouter

from app.api.dependencies import COOKIE_NAME  # noqa: F401  (used by tests)
from app.web import auth_pages, expense_pages, group_pages, notification_pages
from app.web.common import (  # noqa: F401  (re-exported for app.main and tests)
    LoginRequiredError,
    OptionalUser,
    group_error_handler,
    login_required_handler,
    safe_next,
)

router = APIRouter(include_in_schema=False)
router.include_router(auth_pages.router)
router.include_router(group_pages.router)
router.include_router(expense_pages.router)
router.include_router(notification_pages.router)

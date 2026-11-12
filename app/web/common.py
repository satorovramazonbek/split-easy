"""Shared helpers of the HTML pages: rendering, redirects, the login cookie.

After login the JWT is kept in an HttpOnly cookie: JavaScript cannot read it
(safer than localStorage against XSS), and ``SameSite=Lax`` stops other sites
from submitting our forms with it. The JSON API uses the Bearer header.

Messages after a redirect ("flash") are passed as a fixed key in ``?msg=``; the
page shows the text for that key, so no user input is echoed from the URL.
"""

from typing import Annotated, Any
from urllib.parse import quote

from fastapi import Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.api.dependencies import COOKIE_NAME, AuthServiceDep, NotificationServiceDep
from app.domain.models import User
from app.infrastructure.config import settings
from app.services.auth_service import InvalidCredentialsError
from app.services.group_service import GroupError, GroupNotFoundError
from app.web.templating import templates

DEFAULT_PAGE = "/groups"

FLASH: dict[str, tuple[str, str]] = {
    "welcome": ("success", "Xush kelibsiz! Hisobingiz yaratildi."),
    "logged_out": ("info", "Tizimdan chiqdingiz."),
    "login_required": ("warning", "Davom etish uchun tizimga kiring."),
    "group_created": ("success", "Guruh yaratildi."),
    "group_deleted": ("info", "Guruh o'chirildi."),
    "member_added": ("success", "A'zo qo'shildi."),
    "member_removed": ("info", "A'zo guruhdan chiqarildi."),
    "user_not_found": ("danger", "Bunday foydalanuvchi topilmadi."),
    "already_member": ("warning", "Bu foydalanuvchi allaqachon guruhda."),
    "member_not_found": ("warning", "Bu foydalanuvchi guruhda emas."),
    "owner_cannot_leave": ("danger", "Guruh egasini chiqarib bo'lmaydi."),
    "member_has_debt": (
        "danger",
        "A'zoning balansi 0 emas — avval hisob-kitob qilinishi kerak.",
    ),
    "owner_only": ("danger", "Bu amalni faqat guruh egasi bajara oladi."),
    "expense_added": ("success", "Xarajat saqlandi."),
    "expense_updated": ("success", "Xarajat yangilandi."),
    "expense_deleted": ("info", "Xarajat o'chirildi."),
    "expense_not_found": ("warning", "Xarajat topilmadi."),
    "expense_forbidden": (
        "danger",
        "Xarajatni faqat uni qo'shgan foydalanuvchi yoki guruh egasi o'zgartira oladi.",
    ),
    "settlement_added": ("success", "To'lov saqlandi, balanslar yangilandi."),
    "settlement_forbidden": (
        "danger",
        "To'lovni faqat uning ishtirokchisi yoki guruh egasi belgilay oladi.",
    ),
    "settlement_invalid": (
        "danger",
        "To'lov saqlanmadi: summa qarzdan oshmasligi kerak (balki allaqachon to'langan).",
    ),
    "notifications_read": ("info", "Barcha bildirishnomalar o'qildi."),
}


class LoginRequiredError(Exception):
    """Raised by page dependencies; turned into a redirect to /login."""

    def __init__(self, next_path: str) -> None:
        self.next_path = next_path


def safe_next(value: str | None) -> str:
    """Only local paths, so ?next= cannot send the user to another site."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return DEFAULT_PAGE
    if "\\" in value or "://" in value:
        return DEFAULT_PAGE
    return value


def flash(request: Request) -> tuple[str, str] | None:
    return FLASH.get(request.query_params.get("msg", ""))


def render(
    request: Request, name: str, status_code: int = 200, **context: Any
) -> HTMLResponse:
    context.setdefault("flash", flash(request))
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def redirect(path: str, msg: str | None = None) -> RedirectResponse:
    url = f"{path}?msg={msg}" if msg else path
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


def set_login_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.access_token_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def optional_user(request: Request, auth: AuthServiceDep) -> User | None:
    """The signed-in user from the cookie, or None for a guest."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        return auth.get_current_user(token)
    except InvalidCredentialsError:
        return None


OptionalUser = Annotated[User | None, Depends(optional_user)]


def required_user(request: Request, user: OptionalUser) -> User:
    """Pages for signed-in users only; a guest is sent to /login."""
    if user is None:
        raise LoginRequiredError(request.url.path)
    request.state.user = user  # for the error page navbar
    return user


def page_user(
    request: Request,
    user: Annotated[User, Depends(required_user)],
    notifications: NotificationServiceDep,
) -> User:
    """``required_user`` + the unread count for the navbar bell."""
    request.state.unread = notifications.unread_count(user)
    return user


PageUser = Annotated[User, Depends(page_user)]


# --- error handlers (registered in app.main) ---------------------------------


def login_required_handler(request: Request, exc: LoginRequiredError) -> Response:
    response = RedirectResponse(
        f"/login?msg=login_required&next={quote(exc.next_path)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    if request.cookies.get(COOKIE_NAME):  # expired or invalid token
        response.delete_cookie(COOKIE_NAME, path="/")
    return response


def group_error_handler(request: Request, exc: GroupError) -> Response:
    """HTML error page for a missing group (404) or a non-member (403)."""
    not_found = isinstance(exc, GroupNotFoundError)
    return render(
        request,
        "error.html",
        status_code=404 if not_found else 403,
        code=404 if not_found else 403,
        message=str(exc),
        flash=None,
        user=getattr(request.state, "user", None),
    )

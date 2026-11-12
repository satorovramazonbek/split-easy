"""Server-rendered HTML pages (Jinja2 + Bootstrap).

The pages use the same services as the JSON API. After login the JWT is kept in
an HttpOnly cookie: JavaScript cannot read it (safer than localStorage against
XSS), and ``SameSite=Lax`` stops other sites from submitting our forms with it.
The JSON API keeps using the ``Authorization: Bearer`` header only.

Messages after a redirect ("flash") are passed as a fixed key in ``?msg=``; the
page shows the text for that key, so no user input is echoed from the URL.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError

from app.api.auth import RegisterRequest
from app.api.dependencies import (
    COOKIE_NAME,
    AuthServiceDep,
    ExpenseServiceDep,
    GroupServiceDep,
    NotificationServiceDep,
    ReportServiceDep,
)
from app.domain.exceptions import InvalidSplitError
from app.domain.models import Category, SplitType, User
from app.domain.settlement import simplify_debts
from app.domain.split_strategies import Participant
from app.infrastructure.config import settings
from app.services.auth_service import InvalidCredentialsError, UserAlreadyExistsError
from app.services.expense_service import (
    ExpenseData,
    ExpenseError,
    ExpenseNotFoundError,
    ExpensePermissionError,
)
from app.services.group_service import (
    AlreadyMemberError,
    GroupError,
    GroupNotFoundError,
    GroupPermissionError,
    InvalidGroupError,
    MemberHasHistoryError,
    MemberNotFoundError,
    OwnerCannotLeaveError,
    UserNotFoundError,
)
from app.web.templating import templates

router = APIRouter(include_in_schema=False)

DEFAULT_PAGE = "/groups"

FLASH = {
    "welcome": ("success", "Xush kelibsiz! Hisobingiz yaratildi."),
    "logged_out": ("info", "Tizimdan chiqdingiz."),
    "login_required": ("warning", "Davom etish uchun tizimga kiring."),
    "group_created": ("success", "Guruh yaratildi."),
    "group_deleted": ("info", "Guruh o'chirildi."),
    "member_added": ("success", "A'zo qo'shildi."),
    "member_removed": ("info", "A'zo guruhdan chiqarildi."),
    "expense_added": ("success", "Xarajat saqlandi."),
    "expense_deleted": ("info", "Xarajat o'chirildi."),
    "settlement_added": ("success", "To'lov saqlandi, balanslar yangilandi."),
    "expense_not_found": ("warning", "Xarajat topilmadi."),
    "expense_forbidden": (
        "danger",
        "Xarajatni faqat uni qo'shgan foydalanuvchi yoki guruh egasi o'chira oladi.",
    ),
    "settlement_forbidden": (
        "danger",
        "To'lovni faqat uning ishtirokchisi yoki guruh egasi belgilay oladi.",
    ),
    "settlement_invalid": ("danger", "To'lov ma'lumotlari noto'g'ri."),
    "notifications_read": ("info", "Barcha bildirishnomalar o'qildi."),
}

# Group errors that are shown on the group page as a flash message.
GROUP_ERROR_FLASH = {
    UserNotFoundError: "user_not_found",
    AlreadyMemberError: "already_member",
    MemberNotFoundError: "member_not_found",
    OwnerCannotLeaveError: "owner_cannot_leave",
    MemberHasHistoryError: "member_has_history",
    GroupPermissionError: "owner_only",
}
FLASH.update(
    {
        "user_not_found": ("danger", "Bunday foydalanuvchi topilmadi."),
        "already_member": ("warning", "Bu foydalanuvchi allaqachon guruhda."),
        "member_not_found": ("warning", "Bu foydalanuvchi guruhda emas."),
        "owner_cannot_leave": ("danger", "Guruh egasini chiqarib bo'lmaydi."),
        "member_has_history": (
            "danger",
            "A'zoning guruhda xarajat yoki to'lovlari bor, uni chiqarib bo'lmaydi.",
        ),
        "owner_only": ("danger", "Bu amalni faqat guruh egasi bajara oladi."),
    }
)

REGISTER_ERRORS = {
    "username": "Foydalanuvchi nomi 3–32 belgi: lotin harflari, raqamlar, _ yoki .",
    "email": "Email manzili noto'g'ri.",
    "password": "Parol 8–128 belgidan iborat bo'lishi kerak.",
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


def render(request: Request, name: str, status_code: int = 200, **context):
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
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        return auth.get_current_user(token)
    except InvalidCredentialsError:
        return None


OptionalUser = Annotated[User | None, Depends(optional_user)]


def required_user(
    request: Request, user: OptionalUser, notifications: NotificationServiceDep
) -> User:
    if user is None:
        raise LoginRequiredError(request.url.path)
    request.state.user = user  # for the error page navbar
    request.state.unread = notifications.unread_count(user)  # navbar badge
    return user


PageUser = Annotated[User, Depends(required_user)]


# --- Authentication ----------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: OptionalUser, next: str = DEFAULT_PAGE):
    if user is not None:
        return redirect(safe_next(next))
    return render(request, "auth/login.html", next=safe_next(next))


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    auth: AuthServiceDep,
    username: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    next: Annotated[str, Form()] = DEFAULT_PAGE,
):
    try:
        token = auth.login(username, password)
    except InvalidCredentialsError as error:
        return render(
            request,
            "auth/login.html",
            status_code=status.HTTP_400_BAD_REQUEST,
            error=str(error),
            username=username,
            next=safe_next(next),
        )
    response = redirect(safe_next(next))
    set_login_cookie(response, token)
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user: OptionalUser):
    if user is not None:
        return redirect(DEFAULT_PAGE)
    return render(request, "auth/register.html", errors={}, values={})


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    auth: AuthServiceDep,
    username: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
):
    values = {"username": username, "email": email}
    try:
        data = RegisterRequest(username=username, email=email, password=password)
        auth.register(data.username, str(data.email), data.password)
    except ValidationError as error:
        fields = {str(e["loc"][0]) for e in error.errors()}
        errors = {f: REGISTER_ERRORS[f] for f in fields if f in REGISTER_ERRORS}
        return render(
            request,
            "auth/register.html",
            status_code=status.HTTP_400_BAD_REQUEST,
            errors=errors,
            values=values,
        )
    except UserAlreadyExistsError as error:
        return render(
            request,
            "auth/register.html",
            status_code=status.HTTP_409_CONFLICT,
            errors={"form": str(error)},
            values=values,
        )
    response = redirect(DEFAULT_PAGE, "welcome")
    set_login_cookie(response, auth.login(data.username, data.password))
    return response


@router.post("/logout")
def logout() -> RedirectResponse:
    response = redirect("/login", "logged_out")
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


# --- Groups ------------------------------------------------------------------


def _groups_page(request, user, groups, reports, status_code=200, **extra):
    return render(
        request,
        "groups/list.html",
        status_code=status_code,
        user=user,
        groups=groups.list_groups(user),
        overview=reports.user_overview(user),
        **extra,
    )


@router.get("/groups", response_class=HTMLResponse)
def groups_page(
    request: Request,
    user: PageUser,
    groups: GroupServiceDep,
    reports: ReportServiceDep,
):
    return _groups_page(request, user, groups, reports)


@router.post("/groups", response_class=HTMLResponse)
def create_group(
    request: Request,
    user: PageUser,
    groups: GroupServiceDep,
    reports: ReportServiceDep,
    name: Annotated[str, Form()] = "",
    currency: Annotated[str, Form()] = "UZS",
):
    try:
        details = groups.create_group(user, name, currency)
    except InvalidGroupError as error:
        return _groups_page(
            request,
            user,
            groups,
            reports,
            status_code=status.HTTP_400_BAD_REQUEST,
            error=str(error),
            form={"name": name, "currency": currency},
        )
    return redirect(f"/groups/{details.group.id}", "group_created")


EXPENSES_PER_PAGE = 20


def _group_page(
    request: Request,
    user: User,
    group_id: int,
    groups,
    reports,
    expenses,
    *,
    page: int = 1,
    status_code: int = 200,
    **extra,
):
    details = groups.get_group(user, group_id)  # 404 / 403 -> error page
    balances = reports.member_balances(user, group_id)
    # FR-17: the settlement plan from the same balances the table shows.
    try:
        transfers = simplify_debts({b.user_id: b.balance for b in balances})
    except InvalidSplitError:  # balances must add up to 0; show no plan otherwise
        transfers = []
    names = {m.user_id: m.username for m in details.members}
    names.update({b.user_id: b.username for b in balances})
    categories = reports.category_totals(user, group_id)
    monthly = reports.monthly_totals(user, group_id)
    page = max(1, page)
    expense_page = expenses.list_expenses(
        user,
        group_id,
        limit=EXPENSES_PER_PAGE,
        offset=(page - 1) * EXPENSES_PER_PAGE,
    )
    pages = max(1, -(-expense_page.total // EXPENSES_PER_PAGE))
    is_owner = details.group.owner_id == user.id
    extra.setdefault("expense_form", {})
    return render(
        request,
        "groups/detail.html",
        status_code=status_code,
        user=user,
        group=details.group,
        members=details.members,
        is_owner=is_owner,
        balances=balances,
        balance_max=max((abs(b.balance) for b in balances), default=0),
        my_balance=next((b.balance for b in balances if b.user_id == user.id), 0),
        total_spent=sum(b.paid for b in balances),
        transfers=transfers,
        names=names,
        expenses=expense_page.items,
        expense_total=expense_page.total,
        page=min(page, pages),
        pages=pages,
        settlements=list(reversed(expenses.list_settlements(user, group_id)))[:20],
        can_settle=lambda t: is_owner or user.id in (t.from_user_id, t.to_user_id),
        split_types=[
            ("equal", "Teng"),
            ("exact", "Aniq summalar"),
            ("percentage", "Foiz bo'yicha"),
            ("shares", "Ulushlar bo'yicha"),
        ],
        categories_choice=[c.value for c in Category],
        today=date.today().isoformat(),
        categories=categories,
        category_max=max((c.total for c in categories), default=0),
        monthly=monthly,
        monthly_max=max((m.total for m in monthly), default=0),
        top_payers=reports.top_payers(user, group_id),
        inactive=reports.inactive_members(user, group_id),
        above_average=reports.above_average_expenses(user, group_id),
        running=reports.running_total(user, group_id),
        **extra,
    )


@router.get("/groups/{group_id}", response_class=HTMLResponse)
def group_page(
    request: Request,
    group_id: int,
    user: PageUser,
    groups: GroupServiceDep,
    reports: ReportServiceDep,
    expenses: ExpenseServiceDep,
    page: int = 1,
):
    return _group_page(request, user, group_id, groups, reports, expenses, page=page)


def _int_or_none(value) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _decimal_or_none(value) -> Decimal | None:
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


@router.post("/groups/{group_id}/expenses", response_class=HTMLResponse)
async def add_expense(
    request: Request,
    group_id: int,
    user: PageUser,
    groups: GroupServiceDep,
    reports: ReportServiceDep,
    expenses: ExpenseServiceDep,
):
    form = await request.form()
    split_type = str(form.get("split_type", SplitType.EQUAL.value))
    chosen = [_int_or_none(v) for v in form.getlist("participants")]
    chosen = [c for c in dict.fromkeys(chosen) if c is not None]
    values = {c: str(form.get(f"value_{c}", "")).strip() for c in chosen}
    keep = {
        "description": str(form.get("description", "")),
        "amount": str(form.get("amount", "")),
        "paid_by": _int_or_none(form.get("paid_by")),
        "split_type": split_type,
        "category": str(form.get("category", Category.OTHER.value)),
        "expense_date": str(form.get("expense_date", "")),
        "participants": set(chosen),
        "share_values": values,
    }

    def fail(message: str):
        return _group_page(
            request,
            user,
            group_id,
            groups,
            reports,
            expenses,
            status_code=status.HTTP_400_BAD_REQUEST,
            expense_error=message,
            expense_form=keep,
        )

    amount = _int_or_none(keep["amount"])
    if amount is None or amount <= 0:
        return fail("Summani musbat butun son ko'rinishida kiriting")
    if keep["paid_by"] is None:
        return fail("Kim to'laganini tanlang")
    try:
        expense_date = (
            date.fromisoformat(keep["expense_date"]) if keep["expense_date"] else None
        )
    except ValueError:
        return fail("Sana noto'g'ri")
    participants = []
    for user_id in chosen:
        value = None
        if split_type != SplitType.EQUAL.value:
            value = _decimal_or_none(values[user_id])
            if value is None:
                return fail("Har bir tanlangan ishtirokchi uchun qiymat kiriting")
        participants.append(Participant(user_id, value))
    try:
        expenses.add_expense(
            user,
            group_id,
            ExpenseData(
                description=keep["description"],
                amount=amount,
                paid_by=keep["paid_by"],
                split_type=split_type,
                category=keep["category"],
                expense_date=expense_date,
                participants=participants,
            ),
        )
    except ExpenseError as error:
        return fail(str(error))
    return redirect(f"/groups/{group_id}", "expense_added")


@router.post("/groups/{group_id}/expenses/{expense_id}/delete")
def delete_expense(
    group_id: int, expense_id: int, user: PageUser, expenses: ExpenseServiceDep
):
    try:
        expenses.delete_expense(user, group_id, expense_id)
    except ExpenseNotFoundError:
        return redirect(f"/groups/{group_id}", "expense_not_found")
    except ExpensePermissionError:
        return redirect(f"/groups/{group_id}", "expense_forbidden")
    return redirect(f"/groups/{group_id}", "expense_deleted")


@router.post("/groups/{group_id}/settlements")
def add_settlement(
    group_id: int,
    user: PageUser,
    expenses: ExpenseServiceDep,
    from_user_id: Annotated[int, Form()],
    to_user_id: Annotated[int, Form()],
    amount: Annotated[int, Form()],
):
    try:
        expenses.record_settlement(user, group_id, from_user_id, to_user_id, amount)
    except ExpensePermissionError:
        return redirect(f"/groups/{group_id}", "settlement_forbidden")
    except ExpenseError:
        return redirect(f"/groups/{group_id}", "settlement_invalid")
    return redirect(f"/groups/{group_id}", "settlement_added")


# --- Notifications -------------------------------------------------------------


@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(
    request: Request, user: PageUser, notifications: NotificationServiceDep
):
    return render(
        request,
        "notifications.html",
        user=user,
        notifications=notifications.list(user, limit=50),
    )


@router.post("/notifications/read-all")
def notifications_read_all(user: PageUser, notifications: NotificationServiceDep):
    notifications.mark_all_read(user)
    return redirect("/notifications", "notifications_read")


def _group_action(group_id: int, action, success_msg: str, success_path=None):
    try:
        action()
    except (GroupNotFoundError, InvalidGroupError):
        raise
    except GroupError as error:
        key = GROUP_ERROR_FLASH.get(type(error))
        if key is None:
            raise
        return redirect(f"/groups/{group_id}", key)
    return redirect(success_path or f"/groups/{group_id}", success_msg)


@router.post("/groups/{group_id}/members")
def add_member(
    group_id: int,
    user: PageUser,
    groups: GroupServiceDep,
    login: Annotated[str, Form()] = "",
):
    return _group_action(
        group_id, lambda: groups.add_member(user, group_id, login), "member_added"
    )


@router.post("/groups/{group_id}/members/{member_id}/remove")
def remove_member(
    group_id: int, member_id: int, user: PageUser, groups: GroupServiceDep
):
    return _group_action(
        group_id,
        lambda: groups.remove_member(user, group_id, member_id),
        "member_removed",
    )


@router.post("/groups/{group_id}/delete")
def delete_group(group_id: int, user: PageUser, groups: GroupServiceDep):
    return _group_action(
        group_id,
        lambda: groups.delete_group(user, group_id),
        "group_deleted",
        success_path=DEFAULT_PAGE,
    )


# --- Error handlers (registered in app.main) -----------------------------------


def login_required_handler(request: Request, exc: LoginRequiredError):
    from urllib.parse import quote

    response = RedirectResponse(
        f"/login?msg=login_required&next={quote(exc.next_path)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    if request.cookies.get(COOKIE_NAME):  # expired or invalid token
        response.delete_cookie(COOKIE_NAME, path="/")
    return response


def group_error_handler(request: Request, exc: GroupError):
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

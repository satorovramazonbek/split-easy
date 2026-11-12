"""FastAPI dependencies: wiring of services and the current user."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.domain.events import EventBus
from app.domain.models import User
from app.infrastructure.config import settings
from app.infrastructure.database import get_session
from app.infrastructure.email import FakeEmailSender
from app.infrastructure.security import Argon2PasswordHasher, JwtTokenService
from app.repositories.sqlalchemy.group_repository import SqlAlchemyGroupRepository
from app.repositories.sqlalchemy.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from app.repositories.sqlalchemy.quick_split_draft_repository import (
    SqlAlchemyQuickSplitDraftRepository,
)
from app.repositories.sqlalchemy.report_repository import SqlAlchemyReportRepository
from app.repositories.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from app.repositories.sqlalchemy.user_repository import SqlAlchemyUserRepository
from app.services.auth_service import AuthService, InvalidCredentialsError
from app.services.expense_service import ExpenseService
from app.services.export_service import ExportService
from app.services.group_service import GroupService
from app.services.notification_service import NotificationService
from app.services.notifiers import EmailNotifier, InAppNotifier, register_notifier
from app.services.quick_split_draft_service import QuickSplitDraftService
from app.services.report_service import ReportService
from app.services.settlement_service import SettlementService

# The web pages keep the JWT in this HttpOnly cookie (see app/web/pages.py).
COOKIE_NAME = "spliteasy_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False
)

password_hasher = Argon2PasswordHasher()
token_service = JwtTokenService(settings.secret_key, settings.access_token_minutes)

SessionDep = Annotated[Session, Depends(get_session)]


def get_auth_service(session: SessionDep) -> AuthService:
    return AuthService(
        SqlAlchemyUserRepository(session), password_hasher, token_service
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], auth: AuthServiceDep
) -> User:
    try:
        return auth.get_current_user(token)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_page_or_api_user(
    request: Request,
    auth: AuthServiceDep,
    token: Annotated[str | None, Depends(optional_oauth2_scheme)],
) -> User:
    """Bearer token (API clients) or the login cookie (JavaScript on our pages).

    With the cookie, a write must be sent as JSON: a form on another site
    cannot set ``Content-Type: application/json`` without a CORS preflight,
    which this app does not allow, so the cookie cannot be abused (CSRF).
    """
    if token is None:
        token = request.cookies.get(COOKIE_NAME)
        content_type = request.headers.get("content-type", "")
        if (
            token
            and request.method not in SAFE_METHODS
            and not content_type.startswith("application/json")
        ):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="JSON kutilgan",
            )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_current_user(token, auth)


PageOrApiUser = Annotated[User, Depends(get_page_or_api_user)]


def get_group_service(session: SessionDep) -> GroupService:
    # FastAPI caches ``get_session`` per request, so auth and groups share
    # one session and one transaction.
    return GroupService(
        SqlAlchemyGroupRepository(session),
        SqlAlchemyUserRepository(session),
        SqlAlchemyReportRepository(session),
    )


GroupServiceDep = Annotated[GroupService, Depends(get_group_service)]


def get_report_service(session: SessionDep) -> ReportService:
    return ReportService(
        SqlAlchemyReportRepository(session), SqlAlchemyGroupRepository(session)
    )


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


# One fake sender for the whole app: it only writes emails to the log (FR-22).
email_sender = FakeEmailSender(keep=False)


def get_event_bus(session: SessionDep) -> EventBus:
    """Observer wiring: who reacts to ExpenseAdded / SettlementRecorded.

    The in-app notifier uses the request's session, so its rows are saved in
    the same transaction as the expense or settlement. A new channel is one
    more ``register_notifier`` line here; the services do not change.
    """
    bus = EventBus()
    register_notifier(bus, InAppNotifier(SqlAlchemyNotificationRepository(session)))
    register_notifier(
        bus, EmailNotifier(email_sender, SqlAlchemyUserRepository(session))
    )
    return bus


EventBusDep = Annotated[EventBus, Depends(get_event_bus)]


def get_expense_service(session: SessionDep, events: EventBusDep) -> ExpenseService:
    return ExpenseService(SqlAlchemyUnitOfWork(session), events)


ExpenseServiceDep = Annotated[ExpenseService, Depends(get_expense_service)]


def get_settlement_service(
    session: SessionDep, events: EventBusDep
) -> SettlementService:
    return SettlementService(
        SqlAlchemyUnitOfWork(session), SqlAlchemyReportRepository(session), events
    )


SettlementServiceDep = Annotated[SettlementService, Depends(get_settlement_service)]


def get_export_service(
    expenses: ExpenseServiceDep, groups: GroupServiceDep
) -> ExportService:
    return ExportService(expenses, groups)


ExportServiceDep = Annotated[ExportService, Depends(get_export_service)]


def get_notification_service(session: SessionDep) -> NotificationService:
    return NotificationService(SqlAlchemyNotificationRepository(session))


NotificationServiceDep = Annotated[
    NotificationService, Depends(get_notification_service)
]


def get_draft_service(session: SessionDep) -> QuickSplitDraftService:
    return QuickSplitDraftService(SqlAlchemyQuickSplitDraftRepository(session))


DraftServiceDep = Annotated[QuickSplitDraftService, Depends(get_draft_service)]

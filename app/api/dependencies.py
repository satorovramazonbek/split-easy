"""FastAPI dependencies: wiring of services and the current user."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.domain.models import User
from app.infrastructure.config import settings
from app.infrastructure.database import get_session
from app.infrastructure.security import Argon2PasswordHasher, JwtTokenService
from app.repositories.sqlalchemy.group_repository import SqlAlchemyGroupRepository
from app.repositories.sqlalchemy.report_repository import SqlAlchemyReportRepository
from app.repositories.sqlalchemy.user_repository import SqlAlchemyUserRepository
from app.services.auth_service import AuthService, InvalidCredentialsError
from app.services.group_service import GroupService
from app.services.report_service import ReportService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

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


def get_group_service(session: SessionDep) -> GroupService:
    # FastAPI caches ``get_session`` per request, so auth and groups share
    # one session and one transaction.
    return GroupService(
        SqlAlchemyGroupRepository(session), SqlAlchemyUserRepository(session)
    )


GroupServiceDep = Annotated[GroupService, Depends(get_group_service)]


def get_report_service(session: SessionDep) -> ReportService:
    return ReportService(
        SqlAlchemyReportRepository(session), SqlAlchemyGroupRepository(session)
    )


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]

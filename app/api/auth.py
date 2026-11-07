"""Auth API: registration, login (JWT) and the current user."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field

from app.api.dependencies import AuthServiceDep, CurrentUser
from app.domain.models import User
from app.services.auth_service import InvalidCredentialsError, UserAlreadyExistsError

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

    @classmethod
    def from_domain(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
        )


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, auth: AuthServiceDep) -> UserOut:
    try:
        user = auth.register(request.username, request.email, request.password)
    except UserAlreadyExistsError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    return UserOut.from_domain(user)


@router.post("/login", response_model=TokenOut)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], auth: AuthServiceDep
) -> TokenOut:
    """OAuth2 form: ``username`` field accepts a username or an email."""
    try:
        token = auth.login(form.username, form.password)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    return TokenOut(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.from_domain(user)

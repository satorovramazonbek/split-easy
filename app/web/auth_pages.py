"""Login, registration and logout pages (FR-1 - FR-3)."""

from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError

from app.api.auth import RegisterRequest
from app.api.dependencies import COOKIE_NAME, AuthServiceDep
from app.services.auth_service import InvalidCredentialsError, UserAlreadyExistsError
from app.web.common import (
    DEFAULT_PAGE,
    OptionalUser,
    redirect,
    render,
    safe_next,
    set_login_cookie,
)

router = APIRouter(include_in_schema=False)

REGISTER_ERRORS = {
    "username": "Foydalanuvchi nomi 3–32 belgi: lotin harflari, raqamlar, _ yoki .",
    "email": "Email manzili noto'g'ri.",
    "password": "Parol 8–128 belgidan iborat bo'lishi kerak.",
}


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request, user: OptionalUser, next: str = DEFAULT_PAGE
) -> Response:
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
) -> Response:
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
def register_page(request: Request, user: OptionalUser) -> Response:
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
) -> Response:
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

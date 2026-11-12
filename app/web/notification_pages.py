"""Notifications page (FR-20, FR-21, FR-23)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from app.api.dependencies import NotificationServiceDep
from app.web.common import PageUser, redirect, render

router = APIRouter(include_in_schema=False)


@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(
    request: Request, user: PageUser, notifications: NotificationServiceDep
) -> Response:
    return render(
        request,
        "notifications.html",
        user=user,
        notifications=notifications.list(user, limit=50),
    )


@router.post("/notifications/read-all")
def notifications_read_all(
    user: PageUser, notifications: NotificationServiceDep
) -> Response:
    notifications.mark_all_read(user)
    return redirect("/notifications", "notifications_read")

"""In-app notifications of the current user."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.dependencies import CurrentUser, NotificationServiceDep
from app.services.notification_service import NotificationNotFoundError

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: int
    message: str
    is_read: bool
    created_at: datetime


class UnreadCount(BaseModel):
    unread: int


class MarkedCount(BaseModel):
    marked: int


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    user: CurrentUser,
    notifications: NotificationServiceDep,
    unread_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
) -> list[NotificationOut]:
    return [
        NotificationOut(
            id=n.id, message=n.message, is_read=n.is_read, created_at=n.created_at
        )
        for n in notifications.list(user, unread_only=unread_only, limit=limit)
    ]


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(
    user: CurrentUser, notifications: NotificationServiceDep
) -> UnreadCount:
    return UnreadCount(unread=notifications.unread_count(user))


@router.post("/read-all", response_model=MarkedCount)
def mark_all_read(
    user: CurrentUser, notifications: NotificationServiceDep
) -> MarkedCount:
    return MarkedCount(marked=notifications.mark_all_read(user))


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int, user: CurrentUser, notifications: NotificationServiceDep
) -> NotificationOut:
    """FR-23: only the owner can mark it; someone else's looks missing (404)."""
    try:
        n = notifications.mark_read(user, notification_id)
    except NotificationNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return NotificationOut(
        id=n.id, message=n.message, is_read=n.is_read, created_at=n.created_at
    )

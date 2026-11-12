"""In-app notifications (DESIGN.md: NotificationService).

Notifications are written by ``ExpenseService`` in the same transaction as the
expense or settlement they describe; this service only reads and marks them.
"""

from app.domain.models import Notification, User
from app.repositories.interfaces.notification_repository import (
    NotificationRepository,
)


class NotificationNotFoundError(Exception):
    """No such notification for this user."""


class NotificationService:
    def __init__(self, notifications: NotificationRepository) -> None:
        self._notifications = notifications

    def list(
        self, user: User, *, unread_only: bool = False, limit: int = 20
    ) -> list[Notification]:
        limit = max(1, min(limit, 100))
        return self._notifications.list_for_user(
            user.id, unread_only=unread_only, limit=limit
        )

    def unread_count(self, user: User) -> int:
        return self._notifications.count_unread(user.id)

    def mark_read(self, user: User, notification_id: int) -> None:
        if not self._notifications.mark_read(notification_id, user.id):
            raise NotificationNotFoundError("Bildirishnoma topilmadi")

    def mark_all_read(self, user: User) -> int:
        unread = self._notifications.list_for_user(
            user.id, unread_only=True, limit=1000
        )
        for notification in unread:
            self._notifications.mark_read(notification.id, user.id)
        return len(unread)

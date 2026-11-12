from collections.abc import Iterable
from typing import Protocol

from app.domain.models import Notification


class NotificationRepository(Protocol):
    def add_many(self, notifications: Iterable[Notification]) -> list[Notification]:
        """One insert for all recipients (e.g. every participant of an expense)."""

    def list_for_user(
        self, user_id: int, *, unread_only: bool = False, limit: int = 20
    ) -> list[Notification]:
        """Newest first."""

    def count_unread(self, user_id: int) -> int: ...

    def get_for_user(self, notification_id: int, user_id: int) -> Notification | None:
        """The notification if it belongs to the user, otherwise None."""

    def mark_read(self, notification_id: int, user_id: int) -> bool:
        """Only the owner can mark it; returns False if it is not theirs."""

    def mark_all_read(self, user_id: int) -> int:
        """Mark every unread notification of the user; returns how many."""

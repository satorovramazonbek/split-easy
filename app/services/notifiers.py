"""Observers that turn domain events into notifications (FR-20, FR-21, FR-22).

Every notifier implements the same small ``Notifier`` interface (ISP), so the
event bus can call any of them without knowing which channel it is:

- ``InAppNotifier`` writes rows to the ``notifications`` table;
- ``EmailNotifier`` sends an email through an ``EmailSender`` (in development
  a fake one that only writes to the log, see ``app/infrastructure/email.py``).

A new channel (SMS, Telegram) is a new class registered with
``register_notifier``; ``ExpenseService`` does not change (Open/Closed).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.domain.events import EventBus, ExpenseAdded, SettlementRecorded
from app.domain.models import Notification
from app.repositories.interfaces.notification_repository import (
    NotificationRepository,
)
from app.repositories.interfaces.user_repository import UserRepository


def money(amount: int) -> str:
    """1250000 -> '1 250 000' (spaces between thousands)."""
    return f"{amount:,}".replace(",", " ")


@dataclass(frozen=True)
class Message:
    """Text for one recipient, shared by all channels."""

    user_id: int
    text: str


def expense_messages(event: ExpenseAdded) -> list[Message]:
    """FR-20: every participant except the author, if their share is not 0."""
    return [
        Message(
            user_id=share.user_id,
            text=(
                f"{event.author_name} «{event.group_name}» guruhiga "
                f"«{event.description}» xarajatini qo'shdi "
                f"({money(event.amount)} {event.currency}). "
                f"Sizning ulushingiz: {money(share.share_amount)} {event.currency}."
            ),
        )
        for share in event.shares
        if share.user_id != event.author_id and share.share_amount > 0
    ]


def settlement_messages(event: SettlementRecorded) -> list[Message]:
    """FR-21: the receiver of the payment, unless they recorded it themselves."""
    if event.to_user_id == event.recorded_by:
        return []
    return [
        Message(
            user_id=event.to_user_id,
            text=(
                f"«{event.group_name}»: {event.from_name} sizga "
                f"{money(event.amount)} {event.currency} to'laganini belgiladi."
            ),
        )
    ]


class Notifier(Protocol):
    """One notification channel. The event bus calls these two methods."""

    def on_expense_added(self, event: ExpenseAdded) -> None: ...

    def on_settlement_recorded(self, event: SettlementRecorded) -> None: ...


def register_notifier(bus: EventBus, notifier: Notifier) -> None:
    """Subscribe both methods of ``notifier`` to their events."""
    bus.subscribe(ExpenseAdded, notifier.on_expense_added)
    bus.subscribe(SettlementRecorded, notifier.on_settlement_recorded)


class InAppNotifier:
    """Writes notifications to the database.

    It uses the same session as the service that published the event, so the
    notification is saved in the same transaction as the expense or settlement
    (technical specification, section 10.4).
    """

    def __init__(
        self,
        notifications: NotificationRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._notifications = notifications
        self._clock = clock

    def on_expense_added(self, event: ExpenseAdded) -> None:
        self._save(expense_messages(event))

    def on_settlement_recorded(self, event: SettlementRecorded) -> None:
        self._save(settlement_messages(event))

    def _save(self, messages: list[Message]) -> None:
        if not messages:
            return
        now = self._clock()
        self._notifications.add_many(
            Notification(id=None, user_id=m.user_id, message=m.text, created_at=now)
            for m in messages
        )


class EmailSender(Protocol):
    """Sends one email. The real SMTP sender would implement the same method."""

    def send(self, to: str, subject: str, body: str) -> None: ...


class EmailNotifier:
    """FR-22: the same messages by email."""

    SUBJECT = "SplitEasy: yangi bildirishnoma"

    def __init__(self, sender: EmailSender, users: UserRepository) -> None:
        self._sender = sender
        self._users = users

    def on_expense_added(self, event: ExpenseAdded) -> None:
        self._send(expense_messages(event))

    def on_settlement_recorded(self, event: SettlementRecorded) -> None:
        self._send(settlement_messages(event))

    def _send(self, messages: list[Message]) -> None:
        if not messages:
            return
        users = self._users.get_many(m.user_id for m in messages)
        for message in messages:
            user = users.get(message.user_id)
            if user is not None:
                self._sender.send(user.email, self.SUBJECT, message.text)

"""Notifiers (Observer subscribers): in-app rows and fake emails (FR-20 - FR-22)."""

from datetime import UTC, datetime
from unittest.mock import Mock

from app.domain.events import EventBus, ExpenseAdded, SettlementRecorded, ShareInfo
from app.domain.models import User
from app.infrastructure.email import FakeEmailSender
from app.repositories.in_memory import (
    InMemoryNotificationRepository,
    InMemoryUserRepository,
)
from app.services.notifiers import (
    EmailNotifier,
    InAppNotifier,
    expense_messages,
    register_notifier,
    settlement_messages,
)

NOW = datetime(2026, 11, 10, tzinfo=UTC)


def expense(author: int = 1) -> ExpenseAdded:
    return ExpenseAdded(
        group_id=1,
        group_name="Sayohat",
        currency="UZS",
        expense_id=5,
        description="Ovqat",
        amount=300_000,
        author_id=author,
        author_name="aziza",
        shares=(ShareInfo(1, 150_000), ShareInfo(2, 150_000), ShareInfo(3, 0)),
    )


def settlement(recorded_by: int) -> SettlementRecorded:
    return SettlementRecorded(
        group_id=1,
        group_name="Sayohat",
        currency="UZS",
        settlement_id=9,
        from_user_id=2,
        from_name="ramazon",
        to_user_id=1,
        to_name="aziza",
        amount=50_000,
        recorded_by=recorded_by,
    )


def test_expense_message_goes_to_participants_except_author_and_zero_share() -> None:
    messages = expense_messages(expense())

    assert [m.user_id for m in messages] == [2]
    assert "150 000 UZS" in messages[0].text


def test_settlement_message_goes_to_the_receiver() -> None:
    assert [m.user_id for m in settlement_messages(settlement(recorded_by=2))] == [1]
    # the owner (user 3) recorded it: still the receiver is notified (FR-21)
    assert [m.user_id for m in settlement_messages(settlement(recorded_by=3))] == [1]
    # the receiver recorded it themselves: nobody needs a message
    assert settlement_messages(settlement(recorded_by=1)) == []


def test_in_app_notifier_saves_rows() -> None:
    repo = InMemoryNotificationRepository()
    notifier = InAppNotifier(repo, clock=lambda: NOW)

    notifier.on_expense_added(expense())
    notifier.on_settlement_recorded(settlement(recorded_by=2))

    assert [(n.user_id, n.is_read) for n in repo.notifications] == [
        (2, False),
        (1, False),
    ]


def test_email_notifier_sends_to_the_users_email() -> None:
    users = InMemoryUserRepository()
    for name in ("aziza", "ramazon"):
        users.add(User(None, name, f"{name}@example.com", "hash"))
    sender = Mock()

    EmailNotifier(sender, users).on_expense_added(expense())

    sender.send.assert_called_once()
    to, subject, body = sender.send.call_args.args
    assert subject == EmailNotifier.SUBJECT
    assert to == "ramazon@example.com"
    assert "Ovqat" in body


def test_fake_email_sender_keeps_and_logs(caplog) -> None:
    sender = FakeEmailSender()

    with caplog.at_level("INFO", logger="spliteasy.email"):
        sender.send("a@example.com", "Mavzu", "Matn")

    assert sender.sent[0].to == "a@example.com"
    assert "a@example.com" in caplog.text


def test_register_notifier_subscribes_both_events() -> None:
    bus = EventBus()
    notifier = Mock()

    register_notifier(bus, notifier)
    bus.publish(expense())
    bus.publish(settlement(recorded_by=2))

    notifier.on_expense_added.assert_called_once()
    notifier.on_settlement_recorded.assert_called_once()

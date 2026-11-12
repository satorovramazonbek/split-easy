"""EventBus (Observer): subscribers are called, publishers do not know them."""

from unittest.mock import Mock

from app.domain.events import EventBus, ExpenseAdded, SettlementRecorded, ShareInfo


def expense_event() -> ExpenseAdded:
    return ExpenseAdded(
        group_id=1,
        group_name="Sayohat",
        currency="UZS",
        expense_id=7,
        description="Ovqat",
        amount=300,
        author_id=1,
        author_name="aziza",
        shares=(ShareInfo(1, 150), ShareInfo(2, 150)),
    )


def test_publish_calls_every_subscriber_of_that_event_type() -> None:
    bus = EventBus()
    first, second = Mock(), Mock()
    bus.subscribe(ExpenseAdded, first)
    bus.subscribe(ExpenseAdded, second)
    event = expense_event()

    bus.publish(event)

    first.assert_called_once_with(event)
    second.assert_called_once_with(event)


def test_subscriber_of_another_event_type_is_not_called() -> None:
    bus = EventBus()
    settlement_handler = Mock()
    bus.subscribe(SettlementRecorded, settlement_handler)

    bus.publish(expense_event())

    settlement_handler.assert_not_called()


def test_publish_without_subscribers_does_nothing() -> None:
    EventBus().publish(expense_event())  # no error

"""Domain events and a small event bus (Observer pattern).

Problem: when an expense or a settlement is saved, several things must happen
(an in-app notification, an email, maybe more later). If ``ExpenseService``
called each of them itself, it would know every notification class and change
whenever a new channel is added (breaks SRP and Open/Closed).

Solution: the service only *publishes* an event ("an expense was added").
Observers *subscribe* to the event type and react to it. The service does not
know who is listening; a new channel is a new subscriber, the service does not
change (technical specification, section 8, pattern 3).

The bus is plain Python, so it belongs to the domain layer and is tested
without a web framework or a database.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ShareInfo:
    """One participant's part of an expense, as carried by the event."""

    user_id: int
    share_amount: int


@dataclass(frozen=True)
class ExpenseAdded:
    """Published after a group expense is stored (FR-20)."""

    group_id: int
    group_name: str
    currency: str
    expense_id: int
    description: str
    amount: int
    author_id: int
    author_name: str
    shares: tuple[ShareInfo, ...]


@dataclass(frozen=True)
class SettlementRecorded:
    """Published after a payment between two members is stored (FR-21)."""

    group_id: int
    group_name: str
    currency: str
    settlement_id: int
    from_user_id: int
    from_name: str
    to_user_id: int
    to_name: str
    amount: int
    recorded_by: int


Event = ExpenseAdded | SettlementRecorded
Handler = Callable[[Event], None]


class EventPublisher(Protocol):
    """What a service needs: only the right to publish (ISP, DIP)."""

    def publish(self, event: Event) -> None: ...


class EventBus:
    """Keeps a list of handlers per event type and calls them in order."""

    def __init__(self) -> None:
        self._handlers: dict[type, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Handler) -> None:
        """Register ``handler`` to be called for every event of ``event_type``."""
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        """Call every handler subscribed to the type of ``event``."""
        for handler in self._handlers[type(event)]:
            handler(event)

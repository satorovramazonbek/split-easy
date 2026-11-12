"""Balances, the settlement plan and recorded payments (FR-16 - FR-18, FR-21).

Single responsibility: payments between members. After a payment is saved the
service publishes ``SettlementRecorded``; the in-app and email notifiers react
to it in the same transaction (Observer, spec 10.4).

A payment may not be larger than the debt: the payer must owe money and the
receiver must be owed money, and the amount is at most the smaller of the two.
This stops a double click on "To'landi" from turning a debt into a credit.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from app.domain.events import EventPublisher, SettlementRecorded
from app.domain.exceptions import DomainError, InvalidSplitError
from app.domain.models import Settlement, User
from app.domain.settlement import Transfer, simplify_debts
from app.repositories.interfaces.errors import ReferenceIntegrityError
from app.repositories.interfaces.report_repository import BalanceReader, MemberBalance
from app.repositories.interfaces.unit_of_work import UnitOfWork
from app.services.group_service import require_member_group
from app.services.messages import translate_error
from app.services.notifiers import money


class SettlementError(Exception):
    """Base class for settlement errors."""


class InvalidSettlementError(SettlementError):
    """Wrong parties or amount."""


class SettlementPermissionError(SettlementError):
    """Only a party of the payment or the group owner may record it."""


class SettlementService:
    def __init__(
        self,
        uow: UnitOfWork,
        balances: BalanceReader,
        events: EventPublisher,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uow = uow
        self._balances = balances
        self._events = events
        self._clock = clock

    def balances(self, user: User, group_id: int) -> list[MemberBalance]:
        """FR-16: net balance of every member (positive = the group owes them)."""
        require_member_group(self._uow.groups, user, group_id)
        return self._balances.member_balances(group_id)

    def settle_plan(self, user: User, group_id: int) -> list[Transfer]:
        """FR-17: the fewest transfers that bring every balance to 0 (greedy)."""
        balances = self.balances(user, group_id)
        try:
            return simplify_debts({b.user_id: b.balance for b in balances})
        except InvalidSplitError:  # balances must add up to 0
            return []

    def record_settlement(
        self, user: User, group_id: int, from_user_id: int, to_user_id: int, amount: int
    ) -> Settlement:
        """FR-18: "paid" - the payment changes both balances."""
        with self._uow as uow:
            group = require_member_group(uow.groups, user, group_id)
            if user.id not in (from_user_id, to_user_id, group.owner_id):
                raise SettlementPermissionError(
                    "To'lovni faqat uning ishtirokchisi yoki guruh egasi belgilay oladi"
                )
            members = {m.user_id: m for m in uow.groups.list_members(group.id)}
            if from_user_id not in members or to_user_id not in members:
                raise InvalidSettlementError("To'lov ishtirokchilari guruh a'zosi emas")
            try:
                settlement = Settlement(
                    id=None,
                    group_id=group.id,
                    from_user_id=from_user_id,
                    to_user_id=to_user_id,
                    amount=amount,
                    created_at=self._clock(),
                )
            except DomainError as error:
                raise InvalidSettlementError(translate_error(str(error))) from error
            self._check_not_more_than_debt(group.id, from_user_id, to_user_id, amount)
            try:
                saved = uow.settlements.add(settlement)
            except ReferenceIntegrityError as error:
                raise InvalidSettlementError(
                    "To'lov ishtirokchilari guruh a'zosi emas"
                ) from error

            names = uow.users.get_many([from_user_id, to_user_id])
            self._events.publish(
                SettlementRecorded(
                    group_id=group.id,
                    group_name=group.name,
                    currency=group.currency,
                    settlement_id=saved.id,
                    from_user_id=from_user_id,
                    from_name=names[from_user_id].username,
                    to_user_id=to_user_id,
                    to_name=names[to_user_id].username,
                    amount=amount,
                    recorded_by=user.id,
                )
            )
            uow.commit()
            return saved

    def list_settlements(self, user: User, group_id: int) -> list[Settlement]:
        require_member_group(self._uow.groups, user, group_id)
        return self._uow.settlements.list_for_group(group_id)

    def _check_not_more_than_debt(
        self, group_id: int, from_user_id: int, to_user_id: int, amount: int
    ) -> None:
        balance = {
            b.user_id: b.balance for b in self._balances.member_balances(group_id)
        }
        debt = -balance.get(from_user_id, 0)  # how much the payer owes
        credit = balance.get(to_user_id, 0)  # how much the receiver is owed
        limit = min(debt, credit)
        if limit <= 0:
            raise InvalidSettlementError(
                "Bu to'lov kerak emas: to'lovchi qarzdor emas yoki oluvchiga qarz yo'q"
            )
        if amount > limit:
            raise InvalidSettlementError(
                f"To'lov summasi qarzdan oshmasligi kerak (ko'pi bilan {money(limit)})"
            )

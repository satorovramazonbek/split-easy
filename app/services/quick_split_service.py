"""Quick split without registration or database.

The service is stateless: the browser keeps participants and expenses in
memory and sends them with every request. Nothing is stored on the server,
so the data disappears when the page is reloaded.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.domain.balance import calculate_balances
from app.domain.exceptions import InvalidSplitError
from app.domain.models import Expense, SplitType
from app.domain.settlement import Transfer, simplify_debts
from app.domain.split_strategies import Participant
from app.domain.split_strategy_factory import split_amount

QUICK_GROUP_ID = 0


@dataclass(frozen=True)
class ExpenseInput:
    """Raw expense data as entered by the user."""

    description: str
    amount: int
    paid_by: int
    split_type: str
    participants: Sequence[Participant]


@dataclass(frozen=True)
class SplitResult:
    """Everything the results screen needs."""

    expenses: list[Expense]
    total: int
    paid: dict[int, int]
    owed: dict[int, int]
    balances: dict[int, int]
    transfers: list[Transfer]


class QuickSplitService:
    """Builds expenses and settlement plans for an anonymous, in-memory group."""

    def build_expense(self, member_ids: Iterable[int], data: ExpenseInput) -> Expense:
        members = set(member_ids)
        if data.paid_by not in members:
            raise InvalidSplitError("Payer must be one of the participants")
        if any(participant.user_id not in members for participant in data.participants):
            raise InvalidSplitError("Unknown participant in expense")

        shares = split_amount(data.amount, data.split_type, data.participants)
        return Expense(
            id=None,
            group_id=QUICK_GROUP_ID,
            description=data.description.strip() or "Xarajat",
            amount=data.amount,
            paid_by=data.paid_by,
            split_type=SplitType(data.split_type),
            shares=tuple(shares),
        )

    def calculate(
        self, member_ids: Sequence[int], expenses: Iterable[ExpenseInput]
    ) -> SplitResult:
        if len(set(member_ids)) != len(member_ids):
            raise InvalidSplitError("Participant ids must be unique")

        built = [self.build_expense(member_ids, expense) for expense in expenses]

        paid = dict.fromkeys(member_ids, 0)
        owed = dict.fromkeys(member_ids, 0)
        for expense in built:
            paid[expense.paid_by] += expense.amount
            for share in expense.shares:
                owed[share.user_id] += share.share_amount

        balances = calculate_balances(built, member_ids=member_ids)
        return SplitResult(
            expenses=built,
            total=sum(expense.amount for expense in built),
            paid=paid,
            owed=owed,
            balances=balances,
            transfers=simplify_debts(balances),
        )

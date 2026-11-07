"""Settlement plan: who pays whom, with as few transfers as possible.

Greedy algorithm: the biggest debtor pays the biggest creditor, then the next
pair is taken, until every balance is ``0``. For ``n`` members it produces at
most ``n - 1`` transfers. Ties are broken by user id, so the result is
deterministic.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.exceptions import InvalidSplitError


@dataclass(frozen=True)
class Transfer:
    """A suggested payment from a debtor to a creditor."""

    from_user_id: int
    to_user_id: int
    amount: int


def _sorted_by_amount(items: list[list[int]]) -> list[list[int]]:
    return sorted(items, key=lambda item: (-item[1], item[0]))


def simplify_debts(balances: Mapping[int, int]) -> list[Transfer]:
    """Turn net balances into a short list of transfers.

    ``balances`` maps user id to net balance (positive: is owed money,
    negative: owes money). The balances must add up to ``0``.
    """
    if sum(balances.values()) != 0:
        raise InvalidSplitError("Balances must add up to 0")

    debtors = _sorted_by_amount(
        [[user_id, -balance] for user_id, balance in balances.items() if balance < 0]
    )
    creditors = _sorted_by_amount(
        [[user_id, balance] for user_id, balance in balances.items() if balance > 0]
    )

    transfers: list[Transfer] = []
    debtor_index = creditor_index = 0
    while debtor_index < len(debtors) and creditor_index < len(creditors):
        debtor = debtors[debtor_index]
        creditor = creditors[creditor_index]
        amount = min(debtor[1], creditor[1])
        transfers.append(Transfer(debtor[0], creditor[0], amount))
        debtor[1] -= amount
        creditor[1] -= amount
        if debtor[1] == 0:
            debtor_index += 1
        if creditor[1] == 0:
            creditor_index += 1
    return transfers

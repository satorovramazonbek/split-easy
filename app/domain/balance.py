"""Balance calculation for group members.

Rules (see the specification, section 4.5):

* the payer of an expense gets ``+amount``;
* every participant gets ``-share_amount``;
* a settlement where A pays B gives A ``+amount`` and B ``-amount``.

A positive balance means the group owes the user money, a negative balance
means the user owes money. The sum of all balances is always ``0``.
"""

from collections import defaultdict
from collections.abc import Iterable

from app.domain.models import Expense, Settlement


def calculate_balances(
    expenses: Iterable[Expense],
    settlements: Iterable[Settlement] = (),
    member_ids: Iterable[int] = (),
) -> dict[int, int]:
    """Return the net balance of every user, keyed by user id.

    ``member_ids`` makes sure members without any activity appear with ``0``.
    """
    balances: defaultdict[int, int] = defaultdict(int)
    for member_id in member_ids:
        balances[member_id] += 0

    for expense in expenses:
        balances[expense.paid_by] += expense.amount
        for share in expense.shares:
            balances[share.user_id] -= share.share_amount

    for settlement in settlements:
        balances[settlement.from_user_id] += settlement.amount
        balances[settlement.to_user_id] -= settlement.amount

    return dict(balances)

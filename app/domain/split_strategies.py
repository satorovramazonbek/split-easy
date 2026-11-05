"""Expense split strategies (Strategy pattern).

Every way of splitting an expense implements the same ``SplitStrategy``
interface. Services only depend on this interface, so a new split method can be
added as a new class without changing existing code (Open/Closed principle).
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.exceptions import InvalidSplitError
from app.domain.models import ExpenseShare
from app.domain.money import split_evenly, validate_amount


@dataclass(frozen=True)
class Participant:
    """A participant of an expense.

    ``value`` meaning depends on the strategy: ignored for equal split,
    an exact amount, a percentage, or a number of shares.
    """

    user_id: int
    value: int | Decimal | None = None


class SplitStrategy(ABC):
    """Common interface for all split strategies."""

    def split(
        self, total: int, participants: Sequence[Participant]
    ) -> list[ExpenseShare]:
        """Split ``total`` between ``participants``.

        The returned shares always add up to exactly ``total``.
        """
        validate_amount(total)
        self._validate_participants(participants)
        amounts = self._calculate(total, participants)
        return [
            ExpenseShare(user_id=participant.user_id, share_amount=amount)
            for participant, amount in zip(participants, amounts, strict=True)
        ]

    @staticmethod
    def _validate_participants(participants: Sequence[Participant]) -> None:
        if not participants:
            raise InvalidSplitError("At least one participant is required")
        user_ids = [participant.user_id for participant in participants]
        if len(set(user_ids)) != len(user_ids):
            raise InvalidSplitError("Each participant can appear only once")

    @abstractmethod
    def _calculate(
        self, total: int, participants: Sequence[Participant]
    ) -> list[int]:
        """Return the amount for each participant, in the same order."""


class EqualSplitStrategy(SplitStrategy):
    """Split the total equally between all participants."""

    def _calculate(
        self, total: int, participants: Sequence[Participant]
    ) -> list[int]:
        return split_evenly(total, len(participants))


class ExactSplitStrategy(SplitStrategy):
    """Each participant pays an exact amount; amounts must add up to total."""

    def _calculate(
        self, total: int, participants: Sequence[Participant]
    ) -> list[int]:
        values: list[int] = []
        for participant in participants:
            value = participant.value
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidSplitError("Exact split requires integer amounts")
            if value < 0:
                raise InvalidSplitError("Exact amounts cannot be negative")
            values.append(value)

        if sum(values) != total:
            raise InvalidSplitError(
                f"Exact amounts sum ({sum(values)}) must equal total ({total})"
            )
        return values

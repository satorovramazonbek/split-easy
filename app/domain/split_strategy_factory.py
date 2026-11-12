"""Factory that creates split strategies by name (Factory pattern).

Callers ask for a strategy by its split type (e.g. ``"percentage"``) and never
reference concrete classes. A new strategy is added by registering it here,
existing code does not change (Open/Closed principle).
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import ClassVar

from app.domain.exceptions import InvalidSplitError, UnknownSplitTypeError
from app.domain.models import ExpenseShare, SplitType
from app.domain.split_strategies import (
    EqualSplitStrategy,
    ExactSplitStrategy,
    Participant,
    PercentageSplitStrategy,
    SharesSplitStrategy,
    SplitStrategy,
)


class SplitStrategyFactory:
    """Creates ``SplitStrategy`` instances by split type."""

    _registry: ClassVar[dict[str, type[SplitStrategy]]] = {
        SplitType.EQUAL.value: EqualSplitStrategy,
        SplitType.EXACT.value: ExactSplitStrategy,
        SplitType.PERCENTAGE.value: PercentageSplitStrategy,
        SplitType.SHARES.value: SharesSplitStrategy,
    }

    @classmethod
    def create(cls, split_type: str | SplitType) -> SplitStrategy:
        """Return a new strategy for ``split_type``."""
        key = str(split_type)
        try:
            strategy_class = cls._registry[key]
        except KeyError:
            raise UnknownSplitTypeError(f"Unknown split type: {key!r}") from None
        return strategy_class()

    @classmethod
    def register(cls, split_type: str, strategy_class: type[SplitStrategy]) -> None:
        """Register a new strategy class under ``split_type``."""
        cls._registry[split_type] = strategy_class

    @classmethod
    def available_types(cls) -> list[str]:
        """Return all registered split type names."""
        return list(cls._registry)


def _normalize_value(
    split_type: str, value: int | Decimal | None
) -> int | Decimal | None:
    """Exact split needs ``int`` amounts; ``Decimal`` such as ``5000`` is converted."""
    if split_type == SplitType.EXACT.value and isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise InvalidSplitError("Exact amounts must be whole numbers")
        return int(value)
    return value


def split_amount(
    amount: int, split_type: str, participants: Sequence[Participant]
) -> list[ExpenseShare]:
    """Shares for ``amount`` with the strategy chosen by name.

    Used by both the quick split page and group expenses, so the same rules
    (and the same rounding) apply everywhere.
    """
    normalized = [
        Participant(p.user_id, _normalize_value(split_type, p.value))
        for p in participants
    ]
    return SplitStrategyFactory.create(split_type).split(amount, normalized)

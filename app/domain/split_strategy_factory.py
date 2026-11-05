"""Factory that creates split strategies by name (Factory pattern).

Callers ask for a strategy by its split type (e.g. ``"percentage"``) and never
reference concrete classes. A new strategy is added by registering it here,
existing code does not change (Open/Closed principle).
"""

from typing import ClassVar

from app.domain.exceptions import UnknownSplitTypeError
from app.domain.models import SplitType
from app.domain.split_strategies import (
    EqualSplitStrategy,
    ExactSplitStrategy,
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

"""Tests for SplitStrategyFactory."""

from collections.abc import Iterator, Sequence

import pytest

from app.domain.exceptions import UnknownSplitTypeError
from app.domain.models import SplitType
from app.domain.split_strategies import (
    EqualSplitStrategy,
    ExactSplitStrategy,
    Participant,
    PercentageSplitStrategy,
    SharesSplitStrategy,
    SplitStrategy,
)
from app.domain.split_strategy_factory import SplitStrategyFactory


@pytest.fixture
def restore_registry() -> Iterator[None]:
    """Keep registrations made in a test from leaking into other tests."""
    saved = dict(SplitStrategyFactory._registry)
    yield
    SplitStrategyFactory._registry = saved


@pytest.mark.parametrize(
    ("split_type", "expected_class"),
    [
        ("equal", EqualSplitStrategy),
        ("exact", ExactSplitStrategy),
        ("percentage", PercentageSplitStrategy),
        ("shares", SharesSplitStrategy),
        (SplitType.PERCENTAGE, PercentageSplitStrategy),
    ],
)
def test_factory_creates_strategy_for_known_type(
    split_type: str, expected_class: type[SplitStrategy]
) -> None:
    strategy = SplitStrategyFactory.create(split_type)

    assert isinstance(strategy, expected_class)


def test_factory_raises_error_for_unknown_type() -> None:
    with pytest.raises(UnknownSplitTypeError):
        SplitStrategyFactory.create("unknown")


def test_factory_allows_registering_new_strategy(restore_registry: None) -> None:
    # Arrange: a new split method added without touching existing code (OCP)
    class PayerTakesAllStrategy(SplitStrategy):
        def _calculate(
            self, total: int, participants: Sequence[Participant]
        ) -> list[int]:
            return [total] + [0] * (len(participants) - 1)

    SplitStrategyFactory.register("payer_takes_all", PayerTakesAllStrategy)

    # Act
    strategy = SplitStrategyFactory.create("payer_takes_all")
    shares = strategy.split(100, [Participant(1), Participant(2)])

    # Assert
    assert [share.share_amount for share in shares] == [100, 0]


def test_factory_lists_available_types() -> None:
    assert set(SplitStrategyFactory.available_types()) >= {
        "equal",
        "exact",
        "percentage",
        "shares",
    }

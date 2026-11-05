"""Domain-level exceptions.

The domain layer raises only these exceptions, so upper layers (services, API)
can map them to proper responses without depending on implementation details.
"""


class DomainError(Exception):
    """Base class for all domain errors."""


class InvalidAmountError(DomainError):
    """Raised when a money amount is not a positive integer."""


class InvalidSplitError(DomainError):
    """Raised when split input (participants, values) is invalid."""


class UnknownSplitTypeError(DomainError):
    """Raised when a split strategy is requested for an unknown type."""

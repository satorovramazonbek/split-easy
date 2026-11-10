from typing import Protocol

from app.domain.models import Settlement


class SettlementRepository(Protocol):
    def add(self, settlement: Settlement) -> Settlement:
        """Raises ``ReferenceIntegrityError`` if a party is not a group member."""

    def list_for_group(self, group_id: int) -> list[Settlement]:
        """Oldest first."""

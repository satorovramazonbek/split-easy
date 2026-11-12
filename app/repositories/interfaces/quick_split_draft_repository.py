"""Storage of the signed-in user's quick split page (one JSON document per user)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class StoredDraft:
    user_id: int
    data: str  # JSON text, validated by the service before it is saved
    updated_at: datetime


class QuickSplitDraftRepository(Protocol):
    def get(self, user_id: int) -> StoredDraft | None: ...

    def save(self, draft: StoredDraft) -> StoredDraft:
        """Insert or replace the user's draft."""

    def delete(self, user_id: int) -> None: ...

"""Saving the quick split page for signed-in users.

Guests: the page lives only in browser memory and is lost on reload.
Signed-in users: the browser sends the page state after every change and it is
kept here, so the calculation is still there after a reload or the next login.

The state uses free-form participant names (not registered users), so it is
stored as one JSON document. Its structure is checked here before it is saved:
ids are unique, every expense points to existing participants and its shares
add up to the amount.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.domain.models import User
from app.repositories.interfaces.quick_split_draft_repository import (
    QuickSplitDraftRepository,
    StoredDraft,
)

MAX_DRAFT_BYTES = 512 * 1024


class InvalidDraftError(Exception):
    """The page state is not consistent and is not saved."""


@dataclass(frozen=True)
class Draft:
    data: dict[str, Any]
    updated_at: datetime


def check_draft(data: dict[str, Any]) -> None:
    """Cross-field rules the request schema cannot express."""
    ids = [p["id"] for p in data["participants"]]
    if len(set(ids)) != len(ids):
        raise InvalidDraftError("Ishtirokchilar id'lari takrorlanmasligi kerak")
    names = [p["name"].strip().lower() for p in data["participants"]]
    if len(set(names)) != len(names):
        raise InvalidDraftError("Ishtirokchilar ismlari takrorlanmasligi kerak")
    known = set(ids)
    expense_ids = [e["id"] for e in data["expenses"]]
    if len(set(expense_ids)) != len(expense_ids):
        raise InvalidDraftError("Xarajatlar id'lari takrorlanmasligi kerak")
    for expense in data["expenses"]:
        people = {expense["paid_by"]}
        people.update(p["user_id"] for p in expense["participants"])
        people.update(s["user_id"] for s in expense["shares"])
        if not people <= known:
            raise InvalidDraftError("Xarajatda noma'lum ishtirokchi bor")
        if sum(s["share_amount"] for s in expense["shares"]) != expense["amount"]:
            raise InvalidDraftError("Ulushlar yig'indisi summaga teng emas")


class QuickSplitDraftService:
    def __init__(
        self,
        drafts: QuickSplitDraftRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._drafts = drafts
        self._clock = clock

    def get(self, user: User) -> Draft | None:
        stored = self._drafts.get(user.id)
        if stored is None:
            return None
        return Draft(json.loads(stored.data), stored.updated_at)

    def save(self, user: User, data: dict[str, Any]) -> Draft:
        check_draft(data)
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        if len(text.encode("utf-8")) > MAX_DRAFT_BYTES:
            raise InvalidDraftError("Hisob juda katta")
        stored = self._drafts.save(StoredDraft(user.id, text, self._clock()))
        return Draft(data, stored.updated_at)

    def clear(self, user: User) -> None:
        self._drafts.delete(user.id)

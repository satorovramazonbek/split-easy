"""SQLAlchemy implementation of ``QuickSplitDraftRepository``."""

from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.repositories.interfaces.quick_split_draft_repository import StoredDraft
from app.repositories.sqlalchemy.orm_models import QuickSplitDraftORM
from app.repositories.sqlalchemy.user_repository import as_utc


class SqlAlchemyQuickSplitDraftRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> StoredDraft | None:
        row = self._session.get(QuickSplitDraftORM, user_id, populate_existing=True)
        if row is None:
            return None
        return StoredDraft(row.user_id, row.data, as_utc(row.updated_at))

    def save(self, draft: StoredDraft) -> StoredDraft:
        # One statement (INSERT ... ON CONFLICT DO UPDATE): two tabs saving at
        # the same time cannot both try to insert the row.
        statement = insert(QuickSplitDraftORM).values(
            user_id=draft.user_id, data=draft.data, updated_at=draft.updated_at
        )
        self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[QuickSplitDraftORM.user_id],
                set_={"data": draft.data, "updated_at": draft.updated_at},
            )
        )
        return draft

    def delete(self, user_id: int) -> None:
        self._session.execute(
            delete(QuickSplitDraftORM).where(QuickSplitDraftORM.user_id == user_id)
        )

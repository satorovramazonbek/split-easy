"""In-memory repositories for service unit tests (moved to the app package).

They live in ``app/repositories/in_memory.py`` as the second implementation of
the repository interfaces; this module keeps the old import path for tests.
"""

from app.repositories.in_memory import (  # noqa: F401
    InMemoryBalanceReader,
    InMemoryGroupRepository,
    InMemoryNotificationRepository,
    InMemoryUnitOfWork,
    InMemoryUserRepository,
)

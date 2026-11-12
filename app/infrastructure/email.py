"""Email sending for development (FR-22).

``FakeEmailSender`` does not connect to a mail server: it writes every email to
the application log (and keeps it in memory), so emails can be seen in the
console during development and checked in tests. A real ``SmtpEmailSender``
would implement the same ``send`` method; nothing else would change.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger("spliteasy.email")


@dataclass(frozen=True)
class SentEmail:
    to: str
    subject: str
    body: str


class FakeEmailSender:
    """Logs emails instead of sending them.

    ``keep=True`` (tests) also stores them in ``sent``; the running app uses
    ``keep=False`` so memory does not grow with every email.
    """

    def __init__(self, keep: bool = True) -> None:
        self.keep = keep
        self.sent: list[SentEmail] = []

    def send(self, to: str, subject: str, body: str) -> None:
        if self.keep:
            self.sent.append(SentEmail(to, subject, body))
        logger.info("EMAIL to=%s subject=%r body=%r", to, subject, body)

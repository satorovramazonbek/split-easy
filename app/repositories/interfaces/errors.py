"""Storage errors that services can catch without knowing SQLAlchemy."""


class ReferenceIntegrityError(Exception):
    """A row points to something that does not exist or is not allowed:
    e.g. the payer or a settlement party is not a member of the group
    (composite foreign key to group_members), or an unknown user."""

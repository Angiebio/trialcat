"""SQLAlchemy declarative base + shared column conventions.

All trialcat models inherit from Base so we have one spot to add cross-cutting
behavior like created_at/updated_at timestamps, soft deletes, or audit hooks
if we ever need them. Today it's intentionally minimal.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Timezone-aware UTC now. Never use datetime.utcnow() — it returns naive."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Root declarative base for all trialcat models.

    Provides `fetched_at` and `updated_at` columns to every table — we always
    want to know "when did this row come from CT.gov" and "when did we last
    touch it" for debugging ETL runs.
    """

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        doc="When we first pulled this record from CT.gov",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
        doc="When we last refreshed this row",
    )

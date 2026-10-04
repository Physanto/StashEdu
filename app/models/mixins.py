from datetime import datetime, timezone

from sqlalchemy.dialects.mysql import DATETIME

from app.extensions import db


def _ahora():
    # MySQL DATETIME no conserva zona: persistimos UTC sin tzinfo.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    """Agrega fechas de creación y última modificación (UTC)."""

    created_at = db.Column(
        db.DateTime().with_variant(DATETIME(fsp=6), "mysql"),
        nullable=False,
        default=_ahora,
    )
    updated_at = db.Column(
        db.DateTime().with_variant(DATETIME(fsp=6), "mysql"),
        nullable=False,
        default=_ahora,
        onupdate=_ahora,
    )

from datetime import datetime, timezone

from sqlalchemy.dialects import mysql

from app.extensions import db

# Tipos que reflejan docs/esquema_bd.sql. En otros motores caen en un entero/fecha genéricos.
TINYINT_UNSIGNED = db.Integer().with_variant(mysql.TINYINT(unsigned=True), "mysql")
SMALLINT_UNSIGNED = db.Integer().with_variant(mysql.SMALLINT(unsigned=True), "mysql")
DATETIME_UTC = db.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def _ahora():
    # MySQL DATETIME no conserva zona: persistimos UTC sin tzinfo.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fecha_iso(valor):
    """Serializa una fecha UTC (sin tzinfo) con sufijo Z para que el cliente sepa la zona."""
    return valor.isoformat() + "Z" if valor else None


class TimestampMixin:
    """Agrega fechas de creación y última modificación (UTC, las escribe la API)."""

    created_at = db.Column(DATETIME_UTC, nullable=False, default=_ahora)
    updated_at = db.Column(
        DATETIME_UTC, nullable=False, default=_ahora, onupdate=_ahora
    )

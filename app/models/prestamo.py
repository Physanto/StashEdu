from sqlalchemy.dialects.mysql import DATETIME

from app.extensions import db
from app.models.mixins import TimestampMixin, _ahora


class Prestamo(TimestampMixin, db.Model):
    __tablename__ = "prestamos"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    activo_id = db.Column(
        db.Integer,
        db.ForeignKey("activos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fecha_prestamo = db.Column(
        db.DateTime().with_variant(DATETIME(fsp=6), "mysql"),
        nullable=False,
        default=_ahora,
    )
    fecha_devolucion_prevista = db.Column(
        db.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False, index=True
    )
    fecha_devolucion = db.Column(db.DateTime().with_variant(DATETIME(fsp=6), "mysql"))
    observaciones = db.Column(db.String(1000))

    __table_args__ = (
        db.CheckConstraint(
            "fecha_devolucion_prevista > fecha_prestamo", name="ck_prestamo_plazo"
        ),
        db.CheckConstraint(
            "fecha_devolucion IS NULL OR fecha_devolucion >= fecha_prestamo",
            name="ck_prestamo_devolucion",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "usuario_id": self.usuario_id,
            "activo_id": self.activo_id,
            "fecha_prestamo": self.fecha_prestamo.isoformat() + "Z",
            "fecha_devolucion_prevista": self.fecha_devolucion_prevista.isoformat()
            + "Z",
            "fecha_devolucion": self.fecha_devolucion.isoformat() + "Z"
            if self.fecha_devolucion
            else None,
            "estado": "devuelto" if self.fecha_devolucion else "activo",
            "retrasado": (self.fecha_devolucion or _ahora())
            > self.fecha_devolucion_prevista,
            "observaciones": self.observaciones,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

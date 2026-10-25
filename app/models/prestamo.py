from datetime import timedelta

from app.extensions import db
from app.models.mixins import DATETIME_UTC, TimestampMixin, _ahora, fecha_iso

# El estado NO se guarda: se deriva de las fechas (ver docs/esquema_bd.sql).
ESTADOS_PRESTAMO = ("activo", "vencido", "devuelto", "devuelto_con_retraso")


class Prestamo(TimestampMixin, db.Model):
    """Un registro por préstamo. Solo guarda hechos (fechas); el estado se calcula."""

    __tablename__ = "prestamos"
    __table_args__ = (
        db.CheckConstraint(
            "fecha_vencimiento > fecha_prestamo", name="chk_prestamos_vencimiento"
        ),
        db.CheckConstraint(
            "fecha_devolucion IS NULL OR fecha_devolucion >= fecha_prestamo",
            name="chk_prestamos_devolucion",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", name="fk_prestamos_usuario", ondelete="RESTRICT"),
        nullable=False,
    )
    activo_id = db.Column(
        db.Integer,
        db.ForeignKey("activos.id", name="fk_prestamos_activo", ondelete="RESTRICT"),
        nullable=False,
    )
    fecha_prestamo = db.Column(DATETIME_UTC, nullable=False)
    fecha_vencimiento = db.Column(DATETIME_UTC, nullable=False)
    fecha_devolucion = db.Column(DATETIME_UTC)  # NULL = préstamo abierto
    observaciones_entrega = db.Column(db.Text)
    observaciones_devolucion = db.Column(db.Text)

    usuario = db.relationship("Usuario", lazy="joined")
    activo = db.relationship("Activo", lazy="joined")

    @property
    def estado(self):
        if self.fecha_devolucion is None:
            return "vencido" if self.fecha_vencimiento < _ahora() else "activo"
        if self.fecha_devolucion > self.fecha_vencimiento:
            return "devuelto_con_retraso"
        return "devuelto"

    @property
    def dias_retraso(self):
        """Días (o fracción de día) pasados después del vencimiento; 0 si va a tiempo."""
        referencia = self.fecha_devolucion or _ahora()
        retraso = referencia - self.fecha_vencimiento
        if retraso <= timedelta(0):
            return 0
        return -(-retraso // timedelta(days=1))  # división redondeando hacia arriba

    @classmethod
    def condicion_estado(cls, estado, ahora):
        """La misma regla de `estado`, escrita como condición SQL para filtrar en la BD."""
        abierto = cls.fecha_devolucion.is_(None)
        condiciones = {
            "activo": db.and_(abierto, cls.fecha_vencimiento >= ahora),
            "vencido": db.and_(abierto, cls.fecha_vencimiento < ahora),
            "devuelto": cls.fecha_devolucion <= cls.fecha_vencimiento,
            "devuelto_con_retraso": cls.fecha_devolucion > cls.fecha_vencimiento,
        }
        return condiciones[estado]

    def to_dict(self):
        return {
            "id": self.id,
            "usuario": {
                "id": self.usuario.id,
                "nombre_completo": self.usuario.nombre_completo,
            },
            "activo": {
                "id": self.activo.id,
                "codigo_inventario": self.activo.codigo_inventario,
                "nombre": self.activo.nombre,
            },
            "fecha_prestamo": fecha_iso(self.fecha_prestamo),
            "fecha_vencimiento": fecha_iso(self.fecha_vencimiento),
            "fecha_devolucion": fecha_iso(self.fecha_devolucion),
            "estado": self.estado,
            "dias_retraso": self.dias_retraso,
            "observaciones_entrega": self.observaciones_entrega,
            "observaciones_devolucion": self.observaciones_devolucion,
            "created_at": fecha_iso(self.created_at),
            "updated_at": fecha_iso(self.updated_at),
        }

    def __repr__(self):
        return f"<Prestamo {self.id} usuario={self.usuario_id} activo={self.activo_id}>"

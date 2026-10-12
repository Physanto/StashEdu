from app.extensions import db
from app.models.mixins import TimestampMixin, fecha_iso

CATEGORIAS = ("portatil", "proyector", "tablet", "camara", "otro")
ESTADOS = ("disponible", "prestado", "mantenimiento", "baja")
# El estado "prestado" está reservado para el flujo de préstamos.
ESTADOS_EDITABLES = ("disponible", "mantenimiento", "baja")


def _en(columna, valores):
    """Arma el texto SQL `columna IN ('a', 'b', ...)` para un CHECK."""
    return f"{columna} IN ({', '.join(repr(v) for v in valores)})"


class Activo(TimestampMixin, db.Model):
    __tablename__ = "activos"
    __table_args__ = (
        db.UniqueConstraint("codigo_inventario", name="uq_activos_codigo_inventario"),
        db.UniqueConstraint("numero_serie", name="uq_activos_numero_serie"),
        db.CheckConstraint(_en("categoria", CATEGORIAS), name="chk_activos_categoria"),
        db.CheckConstraint(_en("estado", ESTADOS), name="chk_activos_estado"),
    )

    id = db.Column(db.Integer, primary_key=True)
    codigo_inventario = db.Column(db.String(30), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(30), nullable=False)
    marca = db.Column(db.String(60))
    modelo = db.Column(db.String(60))
    numero_serie = db.Column(db.String(60))
    estado = db.Column(
        db.String(20), nullable=False, default="disponible", server_default="disponible"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "codigo_inventario": self.codigo_inventario,
            "nombre": self.nombre,
            "categoria": self.categoria,
            "marca": self.marca,
            "modelo": self.modelo,
            "numero_serie": self.numero_serie,
            "estado": self.estado,
            "created_at": fecha_iso(self.created_at),
            "updated_at": fecha_iso(self.updated_at),
        }

    def __repr__(self):
        return f"<Activo {self.id} {self.codigo_inventario}>"

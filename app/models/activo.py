from app.extensions import db
from app.models.mixins import TimestampMixin

CATEGORIAS = ("portatil", "proyector", "tablet", "camara", "otro")
# El estado "prestado" está reservado para el flujo de préstamos.
ESTADOS_EDITABLES = ("disponible", "mantenimiento", "baja")


class Activo(TimestampMixin, db.Model):
    __tablename__ = "activos"

    id = db.Column(db.Integer, primary_key=True)
    codigo_inventario = db.Column(db.String(30), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(30), nullable=False)
    marca = db.Column(db.String(60))
    modelo = db.Column(db.String(60))
    numero_serie = db.Column(db.String(60), unique=True)
    descripcion = db.Column(db.Text)
    estado = db.Column(db.String(20), nullable=False, default="disponible")
    fecha_adquisicion = db.Column(db.Date)

    def to_dict(self):
        return {
            "id": self.id,
            "codigo_inventario": self.codigo_inventario,
            "nombre": self.nombre,
            "categoria": self.categoria,
            "marca": self.marca,
            "modelo": self.modelo,
            "numero_serie": self.numero_serie,
            "descripcion": self.descripcion,
            "estado": self.estado,
            "fecha_adquisicion": (
                self.fecha_adquisicion.isoformat() if self.fecha_adquisicion else None
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f"<Activo {self.id} {self.codigo_inventario}>"

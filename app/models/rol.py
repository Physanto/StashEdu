from app.extensions import db
from app.models.mixins import TINYINT_UNSIGNED

# Códigos de los roles sembrados por la migración de la Fase 3.
ROL_ADMIN = "admin"
ROL_OPERADOR = "operador"
ROL_CONSULTA = "consulta"


class Rol(db.Model):
    """Catálogo de quien OPERA el sistema. Qué puede hacer cada rol se define en app/auth.py."""

    __tablename__ = "roles"
    __table_args__ = (db.UniqueConstraint("codigo", name="uq_roles_codigo"),)

    id = db.Column(TINYINT_UNSIGNED, primary_key=True, autoincrement=True)
    codigo = db.Column(db.String(20), nullable=False)
    descripcion = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {"id": self.id, "codigo": self.codigo, "descripcion": self.descripcion}

    def __repr__(self):
        return f"<Rol {self.id} {self.codigo}>"

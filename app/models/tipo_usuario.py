from app.extensions import db
from app.models.mixins import SMALLINT_UNSIGNED, TINYINT_UNSIGNED


class TipoUsuario(db.Model):
    """Catálogo de quien PIDE prestado (estudiante, docente, funcionario)."""

    __tablename__ = "tipos_usuario"
    __table_args__ = (
        db.UniqueConstraint("codigo", name="uq_tipos_usuario_codigo"),
        db.CheckConstraint(
            "max_prestamos_activos > 0 AND dias_max_prestamo > 0",
            name="chk_tipos_usuario_limites",
        ),
    )

    id = db.Column(TINYINT_UNSIGNED, primary_key=True, autoincrement=True)
    codigo = db.Column(db.String(20), nullable=False)
    descripcion = db.Column(db.String(100), nullable=False)
    max_prestamos_activos = db.Column(TINYINT_UNSIGNED, nullable=False)
    dias_max_prestamo = db.Column(SMALLINT_UNSIGNED, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "codigo": self.codigo,
            "descripcion": self.descripcion,
            "max_prestamos_activos": self.max_prestamos_activos,
            "dias_max_prestamo": self.dias_max_prestamo,
        }

    def __repr__(self):
        return f"<TipoUsuario {self.id} {self.codigo}>"

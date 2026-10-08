from app.extensions import db
from app.models.mixins import TimestampMixin

TIPOS_USUARIO = ("estudiante", "docente", "funcionario")


class Usuario(TimestampMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre_completo = db.Column(db.String(120), nullable=False)
    documento = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    tipo_usuario = db.Column(db.String(20), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    # Nullable permite migrar usuarios históricos sin inventar contraseñas.
    password_hash = db.Column(db.String(255))

    def set_password(self, password):
        from app.security import hash_password

        self.password_hash = hash_password(password)

    def check_password(self, password):
        from app.security import verificar_password

        return verificar_password(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre_completo": self.nombre_completo,
            "documento": self.documento,
            "email": self.email,
            "telefono": self.telefono,
            "tipo_usuario": self.tipo_usuario,
            "activo": self.activo,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f"<Usuario {self.id} {self.email}>"

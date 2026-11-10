from app.extensions import db
from app.models.mixins import TINYINT_UNSIGNED, TimestampMixin, fecha_iso


class Usuario(TimestampMixin, db.Model):
    """Persona que pide prestado. (rol_id y password_hash llegan en la Fase 3)."""

    __tablename__ = "usuarios"
    __table_args__ = (
        db.UniqueConstraint("documento", name="uq_usuarios_documento"),
        db.UniqueConstraint("email", name="uq_usuarios_email"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nombre_completo = db.Column(db.String(120), nullable=False)
    documento = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(20))
    tipo_usuario_id = db.Column(
        TINYINT_UNSIGNED,
        db.ForeignKey("tipos_usuario.id", name="fk_usuarios_tipo", ondelete="RESTRICT"),
        nullable=False,
    )
    habilitado = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    # Nullable permite migrar usuarios históricos sin inventar contraseñas.
    password_hash = db.Column(db.String(255))

    tipo_usuario = db.relationship("TipoUsuario", lazy="joined")

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
            "tipo_usuario_id": self.tipo_usuario_id,
            "tipo_usuario": self.tipo_usuario.codigo,
            "habilitado": self.habilitado,
            "created_at": fecha_iso(self.created_at),
            "updated_at": fecha_iso(self.updated_at),
        }

    def __repr__(self):
        return f"<Usuario {self.id} {self.email}>"

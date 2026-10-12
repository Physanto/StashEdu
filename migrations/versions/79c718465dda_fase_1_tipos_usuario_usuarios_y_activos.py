"""Fase 1: tipos_usuario, usuarios y activos

Generada con `flask db migrate` a partir de los modelos y revisada a mano:
se ordenaron las tablas por dependencia y se agregaron los datos iniciales
de tipos_usuario (autogenerate no crea datos).

Revision ID: 79c718465dda
Revises:

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# Identificadores de revisión de Alembic.
revision = "79c718465dda"
down_revision = None
branch_labels = None
depends_on = None

TINYINT_U = sa.Integer().with_variant(mysql.TINYINT(unsigned=True), "mysql")
SMALLINT_U = sa.Integer().with_variant(mysql.SMALLINT(unsigned=True), "mysql")
DATETIME_UTC = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade():
    tipos_usuario = op.create_table(
        "tipos_usuario",
        sa.Column("id", TINYINT_U, autoincrement=True, nullable=False),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("descripcion", sa.String(length=100), nullable=False),
        sa.Column("max_prestamos_activos", TINYINT_U, nullable=False),
        sa.Column("dias_max_prestamo", SMALLINT_U, nullable=False),
        sa.CheckConstraint(
            "max_prestamos_activos > 0 AND dias_max_prestamo > 0",
            name="chk_tipos_usuario_limites",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo", name="uq_tipos_usuario_codigo"),
    )

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre_completo", sa.String(length=120), nullable=False),
        sa.Column("documento", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("telefono", sa.String(length=20), nullable=True),
        sa.Column("tipo_usuario_id", TINYINT_U, nullable=False),
        sa.Column("habilitado", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", DATETIME_UTC, nullable=False),
        sa.Column("updated_at", DATETIME_UTC, nullable=False),
        sa.ForeignKeyConstraint(
            ["tipo_usuario_id"], ["tipos_usuario.id"],
            name="fk_usuarios_tipo", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("documento", name="uq_usuarios_documento"),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
    )

    op.create_table(
        "activos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo_inventario", sa.String(length=30), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("categoria", sa.String(length=30), nullable=False),
        sa.Column("marca", sa.String(length=60), nullable=True),
        sa.Column("modelo", sa.String(length=60), nullable=True),
        sa.Column("numero_serie", sa.String(length=60), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="disponible", nullable=False),
        sa.Column("created_at", DATETIME_UTC, nullable=False),
        sa.Column("updated_at", DATETIME_UTC, nullable=False),
        sa.CheckConstraint(
            "categoria IN ('portatil', 'proyector', 'tablet', 'camara', 'otro')",
            name="chk_activos_categoria",
        ),
        sa.CheckConstraint(
            "estado IN ('disponible', 'prestado', 'mantenimiento', 'baja')",
            name="chk_activos_estado",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo_inventario", name="uq_activos_codigo_inventario"),
        sa.UniqueConstraint("numero_serie", name="uq_activos_numero_serie"),
    )

    # Datos iniciales: usuarios.tipo_usuario_id los necesita (clave foránea).
    # Valores de ejemplo: ajústalos a la política real de la institución.
    op.bulk_insert(
        tipos_usuario,
        [
            {"codigo": "estudiante", "descripcion": "Estudiante",
             "max_prestamos_activos": 1, "dias_max_prestamo": 3},
            {"codigo": "docente", "descripcion": "Docente",
             "max_prestamos_activos": 3, "dias_max_prestamo": 15},
            {"codigo": "funcionario", "descripcion": "Funcionario",
             "max_prestamos_activos": 2, "dias_max_prestamo": 7},
        ],
    )


def downgrade():
    op.drop_table("activos")
    op.drop_table("usuarios")
    op.drop_table("tipos_usuario")

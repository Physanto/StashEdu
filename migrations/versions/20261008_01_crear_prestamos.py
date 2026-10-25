"""Fase 2: préstamos

Crea la tabla prestamos según docs/esquema_bd.sql. Las columnas entregado_por
y recibido_por dependen del login y se agregan en la Fase 3.
MySQL crea solo los índices de las claves foráneas (usuario_id, activo_id).

Revision ID: 20261008_01
Revises: 79c718465dda

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# Identificadores de revisión de Alembic.
revision = "20261008_01"
down_revision = "79c718465dda"
branch_labels = None
depends_on = None

DATETIME_UTC = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade():
    op.create_table(
        "prestamos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("activo_id", sa.Integer(), nullable=False),
        sa.Column("fecha_prestamo", DATETIME_UTC, nullable=False),
        sa.Column("fecha_vencimiento", DATETIME_UTC, nullable=False),
        sa.Column("fecha_devolucion", DATETIME_UTC, nullable=True),
        sa.Column("observaciones_entrega", sa.Text(), nullable=True),
        sa.Column("observaciones_devolucion", sa.Text(), nullable=True),
        sa.Column("created_at", DATETIME_UTC, nullable=False),
        sa.Column("updated_at", DATETIME_UTC, nullable=False),
        sa.CheckConstraint(
            "fecha_vencimiento > fecha_prestamo", name="chk_prestamos_vencimiento"
        ),
        sa.CheckConstraint(
            "fecha_devolucion IS NULL OR fecha_devolucion >= fecha_prestamo",
            name="chk_prestamos_devolucion",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"],
            name="fk_prestamos_usuario", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["activo_id"], ["activos.id"],
            name="fk_prestamos_activo", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("prestamos")

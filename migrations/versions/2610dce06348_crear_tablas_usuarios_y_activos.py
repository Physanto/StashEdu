"""Crear tablas usuarios y activos

Revision ID: 2610dce06348
Revises:

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# Identificadores de revisión de Alembic.
revision = "2610dce06348"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo_inventario", sa.String(length=30), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("categoria", sa.String(length=30), nullable=False),
        sa.Column("marca", sa.String(length=60), nullable=True),
        sa.Column("modelo", sa.String(length=60), nullable=True),
        sa.Column("numero_serie", sa.String(length=60), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("fecha_adquisicion", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo_inventario"),
        sa.UniqueConstraint("numero_serie"),
    )
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre_completo", sa.String(length=120), nullable=False),
        sa.Column("documento", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("telefono", sa.String(length=20), nullable=True),
        sa.Column("tipo_usuario", sa.String(length=20), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("documento"),
        sa.UniqueConstraint("email"),
    )


def downgrade():
    op.drop_table("usuarios")
    op.drop_table("activos")

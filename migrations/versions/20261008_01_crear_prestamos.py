"""Crear préstamos y conservar el historial mediante claves foráneas."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "20261008_01"
down_revision = "2610dce06348"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("prestamos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("activo_id", sa.Integer(), sa.ForeignKey("activos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fecha_prestamo", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("fecha_devolucion_prevista", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("fecha_devolucion", mysql.DATETIME(fsp=6)),
        sa.Column("observaciones", sa.String(1000)),
        sa.Column("created_at", sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column("updated_at", sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False),
        sa.CheckConstraint("fecha_devolucion_prevista > fecha_prestamo", name="ck_prestamo_plazo"),
        sa.CheckConstraint("fecha_devolucion IS NULL OR fecha_devolucion >= fecha_prestamo", name="ck_prestamo_devolucion"),
    )
    for campo in ("usuario_id", "activo_id", "fecha_devolucion_prevista"):
        op.create_index(f"ix_prestamos_{campo}", "prestamos", [campo])


def downgrade():
    op.drop_table("prestamos")

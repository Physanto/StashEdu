"""Fase 3: roles, cuentas de operadores y quién entrega/recibe cada préstamo

Implementa la parte de docs/esquema_bd.sql que depende del login:
- tabla roles con sus datos iniciales (admin, operador, consulta);
- usuarios.rol_id y el CHECK chk_usuarios_cuenta (rol y contraseña van juntos);
- prestamos.entregado_por y prestamos.recibido_por.

Las cuentas creadas con el autoregistro anterior (contraseña sin rol) no
cumplen el CHECK: se les quita la contraseña. Un admin las vuelve a habilitar
con POST /auth/register.

Revision ID: 20261109_01
Revises: 20261008_02

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# Identificadores de revisión de Alembic.
revision = "20261109_01"
down_revision = "20261008_02"
branch_labels = None
depends_on = None

TINYINT_U = sa.Integer().with_variant(mysql.TINYINT(unsigned=True), "mysql")


def upgrade():
    roles = op.create_table(
        "roles",
        sa.Column("id", TINYINT_U, autoincrement=True, nullable=False),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("descripcion", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo", name="uq_roles_codigo"),
    )
    op.bulk_insert(
        roles,
        [
            {"codigo": "admin", "descripcion": "Administra usuarios, activos y préstamos"},
            {"codigo": "operador", "descripcion": "Entrega y recibe activos"},
            {"codigo": "consulta", "descripcion": "Solo lectura"},
        ],
    )

    op.add_column("usuarios", sa.Column("rol_id", TINYINT_U, nullable=True))
    op.create_foreign_key(
        "fk_usuarios_rol", "usuarios", "roles", ["rol_id"], ["id"], ondelete="RESTRICT"
    )
    op.execute("UPDATE usuarios SET password_hash = NULL WHERE rol_id IS NULL")
    op.create_check_constraint(
        "chk_usuarios_cuenta", "usuarios", "(password_hash IS NULL) = (rol_id IS NULL)"
    )

    for columna in ("entregado_por", "recibido_por"):
        op.add_column("prestamos", sa.Column(columna, sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_prestamos_{columna}", "prestamos", "usuarios",
            [columna], ["id"], ondelete="RESTRICT",
        )


def downgrade():
    for columna in ("recibido_por", "entregado_por"):
        op.drop_constraint(f"fk_prestamos_{columna}", "prestamos", type_="foreignkey")
        op.drop_column("prestamos", columna)

    op.drop_constraint("chk_usuarios_cuenta", "usuarios", type_="check")
    op.drop_constraint("fk_usuarios_rol", "usuarios", type_="foreignkey")
    op.drop_column("usuarios", "rol_id")
    op.drop_table("roles")

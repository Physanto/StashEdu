"""Añadir hash opcional a usuarios existentes sin alterar sus datos."""
from alembic import op
import sqlalchemy as sa

revision = "20261008_02"
down_revision = "20261008_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("password_hash", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("usuarios", "password_hash")

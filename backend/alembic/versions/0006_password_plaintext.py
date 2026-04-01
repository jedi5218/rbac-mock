"""Add plaintext password column for demo quick-login

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password", sa.Text(), nullable=True))
    # Backfill existing users with the known demo password
    op.execute("UPDATE users SET password = 'admin123'")


def downgrade() -> None:
    op.drop_column("users", "password")

"""Add description column to organizations, roles, and resources

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("roles", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("resources", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("resources", "description")
    op.drop_column("roles", "description")
    op.drop_column("organizations", "description")

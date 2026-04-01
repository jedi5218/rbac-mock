"""Replace email with description on users

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("description", sa.Text(), nullable=True))
    op.execute("UPDATE users SET description = 'email: ' || email WHERE email IS NOT NULL")
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.drop_column("users", "email")


def downgrade() -> None:
    op.add_column("users", sa.Column("email", sa.Text(), nullable=True))
    op.execute("""
        UPDATE users SET email = substring(description FROM '^email: (.+)$')
        WHERE description LIKE 'email: %'
    """)
    op.execute("UPDATE users SET email = username || '@example.com' WHERE email IS NULL")
    op.alter_column("users", "email", nullable=False)
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.drop_column("users", "description")

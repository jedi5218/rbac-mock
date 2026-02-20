"""Wire @members inclusion chain: child org @members includes parent org @members

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # For every org that has a parent, insert role_inclusion:
    # child's @members includes parent's @members
    bind.execute(sa.text("""
        INSERT INTO role_inclusions (role_id, included_role_id)
        SELECT child_m.id, parent_m.id
        FROM organizations o
        JOIN organizations parent ON parent.id = o.parent_id
        JOIN roles child_m  ON child_m.org_id  = o.id      AND child_m.is_org_role  = true
        JOIN roles parent_m ON parent_m.org_id = parent.id AND parent_m.is_org_role = true
        ON CONFLICT DO NOTHING
    """))


def downgrade() -> None:
    bind = op.get_bind()
    # Remove inclusions that are between two org-roles
    bind.execute(sa.text("""
        DELETE FROM role_inclusions
        WHERE role_id IN (SELECT id FROM roles WHERE is_org_role = true)
          AND included_role_id IN (SELECT id FROM roles WHERE is_org_role = true)
    """))

"""Add is_public/is_org_role to roles; create @members role per org

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-20
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("roles", sa.Column("is_public",   sa.Boolean, nullable=False, server_default="false"))
    op.add_column("roles", sa.Column("is_org_role", sa.Boolean, nullable=False, server_default="false"))

    bind = op.get_bind()

    # Create @members role for every existing org and add its users
    orgs = bind.execute(sa.text("SELECT id FROM organizations")).fetchall()
    for (org_id,) in orgs:
        role_id = str(uuid.uuid4())
        bind.execute(sa.text("""
            INSERT INTO roles (id, name, org_id, is_public, is_org_role)
            VALUES (:id, '@members', :org_id, true, true)
        """), {"id": role_id, "org_id": str(org_id)})

        users = bind.execute(
            sa.text("SELECT id FROM users WHERE org_id = :org_id"),
            {"org_id": str(org_id)},
        ).fetchall()
        for (user_id,) in users:
            bind.execute(sa.text("""
                INSERT INTO user_roles (user_id, role_id)
                VALUES (:uid, :rid)
                ON CONFLICT DO NOTHING
            """), {"uid": str(user_id), "rid": role_id})


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE is_org_role = true")
    op.drop_column("roles", "is_org_role")
    op.drop_column("roles", "is_public")

"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── organizations ──────────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=True),
    )

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("username", sa.Text, nullable=False, unique=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_superadmin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_org_admin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )

    # ── resources ─────────────────────────────────────────────────────────────
    op.create_table(
        "resources",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("resource_type", sa.Text, nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("resource_type IN ('document','video')", name="ck_resource_type"),
    )

    # ── roles ─────────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.UniqueConstraint("name", "org_id", name="uq_role_name_org"),
    )

    # ── role_inclusions ───────────────────────────────────────────────────────
    op.create_table(
        "role_inclusions",
        sa.Column("role_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("included_role_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.CheckConstraint("role_id != included_role_id", name="ck_no_self_inclusion"),
    )

    # ── role_resource_permissions ─────────────────────────────────────────────
    op.create_table(
        "role_resource_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_bits", sa.Integer, nullable=False),
        sa.CheckConstraint("permission_bits > 0", name="ck_permission_bits_positive"),
    )

    # ── user_roles ────────────────────────────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    # Seed data is now managed by app/seed.py and the POST /reset endpoint.


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("role_resource_permissions")
    op.drop_table("role_inclusions")
    op.drop_table("roles")
    op.drop_table("resources")
    op.drop_table("users")
    op.drop_table("organizations")

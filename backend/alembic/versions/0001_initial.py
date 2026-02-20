"""initial schema + seed data

Revision ID: 0001
Revises:
Create Date: 2026-02-20

"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

import bcrypt
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

    # ── Seed data ─────────────────────────────────────────────────────────────
    bind = op.get_bind()

    # Orgs: root → division → team
    root_id = str(uuid.uuid4())
    division_id = str(uuid.uuid4())
    team_id = str(uuid.uuid4())

    bind.execute(sa.text("""
        INSERT INTO organizations (id, name, parent_id) VALUES
        (:root_id,     'Root Corp',  NULL),
        (:division_id, 'Division A', :root_id),
        (:team_id,     'Team Alpha', :division_id)
    """), {"root_id": root_id, "division_id": division_id, "team_id": team_id})

    # Superadmin user (password: admin123)
    superadmin_id = str(uuid.uuid4())
    pw_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    bind.execute(sa.text("""
        INSERT INTO users (id, username, email, password_hash, org_id, is_superadmin, is_org_admin)
        VALUES (:id, 'admin', 'admin@example.com', :pw, :org_id, true, true)
    """), {"id": superadmin_id, "pw": pw_hash, "org_id": root_id})

    # Sample resources
    doc_id = str(uuid.uuid4())
    vid_id = str(uuid.uuid4())
    bind.execute(sa.text("""
        INSERT INTO resources (id, name, resource_type, org_id) VALUES
        (:doc_id, 'Company Handbook', 'document', :root_id),
        (:vid_id, 'Onboarding Video', 'video',    :division_id)
    """), {"doc_id": doc_id, "vid_id": vid_id, "root_id": root_id, "division_id": division_id})

    # Sample roles
    reader_id = str(uuid.uuid4())
    writer_id = str(uuid.uuid4())
    viewer_id = str(uuid.uuid4())
    bind.execute(sa.text("""
        INSERT INTO roles (id, name, org_id) VALUES
        (:reader_id, 'Reader',  :root_id),
        (:writer_id, 'Writer',  :root_id),
        (:viewer_id, 'Viewer',  :division_id)
    """), {"reader_id": reader_id, "writer_id": writer_id, "viewer_id": viewer_id,
           "root_id": root_id, "division_id": division_id})

    # Permissions: Reader → read doc (bit 1), Writer → write doc (bit 2), Viewer → view+stream video (bit 5)
    bind.execute(sa.text("""
        INSERT INTO role_resource_permissions (role_id, resource_id, permission_bits) VALUES
        (:reader_id, :doc_id, 1),
        (:writer_id, :doc_id, 2),
        (:viewer_id, :vid_id, 5)
    """), {"reader_id": reader_id, "writer_id": writer_id, "viewer_id": viewer_id,
           "doc_id": doc_id, "vid_id": vid_id})

    # Writer includes Reader (inherits read permission)
    bind.execute(sa.text("""
        INSERT INTO role_inclusions (role_id, included_role_id) VALUES (:writer_id, :reader_id)
    """), {"writer_id": writer_id, "reader_id": reader_id})


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("role_resource_permissions")
    op.drop_table("role_inclusions")
    op.drop_table("roles")
    op.drop_table("resources")
    op.drop_table("users")
    op.drop_table("organizations")

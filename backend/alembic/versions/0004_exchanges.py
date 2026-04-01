"""Replace is_public with org exchanges

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create org_exchanges table
    op.create_table(
        "org_exchanges",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_a_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_b_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("org_a_id", "org_b_id", name="uq_exchange_pair"),
        sa.CheckConstraint("org_a_id < org_b_id", name="ck_exchange_ordered_pair"),
        sa.CheckConstraint("org_a_id != org_b_id", name="ck_exchange_different_orgs"),
    )

    # 2. Create exchange_roles table
    op.create_table(
        "exchange_roles",
        sa.Column("exchange_id", UUID(as_uuid=False), sa.ForeignKey("org_exchanges.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", UUID(as_uuid=False), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    # 3. Data migration: create exchanges for existing cross-org public role inclusions
    op.execute(sa.text("""
        WITH RECURSIVE
        -- Build ancestor/descendant pairs to identify hierarchy relationships
        org_tree AS (
            SELECT id AS org_id, id AS related_id FROM organizations
            UNION
            SELECT ot.org_id, o.id
            FROM organizations o JOIN org_tree ot ON o.parent_id = ot.related_id
        ),
        -- Find cross-org role inclusions where the included role is public
        -- and the two orgs are NOT in an ancestor/descendant relationship
        cross_org_links AS (
            SELECT DISTINCT
                LEAST(r1.org_id, r2.org_id) AS org_a,
                GREATEST(r1.org_id, r2.org_id) AS org_b
            FROM role_inclusions ri
            JOIN roles r1 ON ri.role_id = r1.id
            JOIN roles r2 ON ri.included_role_id = r2.id
            WHERE r1.org_id != r2.org_id
              AND r2.is_public = true
              AND NOT EXISTS (
                  SELECT 1 FROM org_tree
                  WHERE org_id = r1.org_id AND related_id = r2.org_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM org_tree
                  WHERE org_id = r2.org_id AND related_id = r1.org_id
              )
        )
        INSERT INTO org_exchanges (id, org_a_id, org_b_id)
        SELECT gen_random_uuid(), org_a, org_b FROM cross_org_links
        ON CONFLICT DO NOTHING
    """))

    # Expose the public roles that were involved in cross-org inclusions
    op.execute(sa.text("""
        WITH RECURSIVE
        org_tree AS (
            SELECT id AS org_id, id AS related_id FROM organizations
            UNION
            SELECT ot.org_id, o.id
            FROM organizations o JOIN org_tree ot ON o.parent_id = ot.related_id
        )
        INSERT INTO exchange_roles (exchange_id, role_id)
        SELECT DISTINCT ex.id, r2.id
        FROM role_inclusions ri
        JOIN roles r1 ON ri.role_id = r1.id
        JOIN roles r2 ON ri.included_role_id = r2.id
        JOIN org_exchanges ex ON (
            (LEAST(r1.org_id, r2.org_id) = ex.org_a_id AND GREATEST(r1.org_id, r2.org_id) = ex.org_b_id)
        )
        WHERE r1.org_id != r2.org_id
          AND r2.is_public = true
          AND NOT EXISTS (
              SELECT 1 FROM org_tree WHERE org_id = r1.org_id AND related_id = r2.org_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM org_tree WHERE org_id = r2.org_id AND related_id = r1.org_id
          )
        ON CONFLICT DO NOTHING
    """))

    # 4. Drop is_public column
    op.drop_column("roles", "is_public")


def downgrade() -> None:
    # 1. Re-add is_public column
    op.add_column("roles", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    # 2. Set is_public=true for roles that were exposed via exchanges
    op.execute(sa.text("""
        UPDATE roles SET is_public = true
        WHERE id IN (SELECT role_id FROM exchange_roles)
    """))

    # 3. Set is_public=true for org roles (they were always public)
    op.execute(sa.text("""
        UPDATE roles SET is_public = true WHERE is_org_role = true
    """))

    # 4. Drop tables
    op.drop_table("exchange_roles")
    op.drop_table("org_exchanges")

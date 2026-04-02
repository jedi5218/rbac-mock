import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=True)

    parent = relationship("Organization", remote_side="Organization.id", back_populates="children")
    children = relationship("Organization", back_populates="parent")
    users = relationship("User", back_populates="org")
    resources = relationship("Resource", back_populates="org")
    roles = relationship("Role", back_populates="org")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    username = Column(Text, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    password_hash = Column(Text, nullable=False)
    password = Column(Text, nullable=True)  # plaintext for demo quick-login
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    is_superadmin = Column(Boolean, default=False, nullable=False)
    is_org_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    org = relationship("Organization", back_populates="users")
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    resource_type = Column(Text, nullable=False)
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)

    __table_args__ = (
        CheckConstraint("resource_type IN ('document', 'video')", name="ck_resource_type"),
    )

    org = relationship("Organization", back_populates="resources")
    permissions = relationship("RoleResourcePermission", back_populates="resource", cascade="all, delete-orphan")


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    is_org_role = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("name", "org_id", name="uq_role_name_org"),
    )

    org = relationship("Organization", back_populates="roles")
    inclusions = relationship(
        "RoleInclusion", foreign_keys="RoleInclusion.role_id",
        back_populates="role", cascade="all, delete-orphan",
    )
    included_by = relationship(
        "RoleInclusion", foreign_keys="RoleInclusion.included_role_id",
        back_populates="included_role", cascade="all, delete-orphan",
    )
    permissions = relationship("RoleResourcePermission", back_populates="role", cascade="all, delete-orphan")
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")


class RoleInclusion(Base):
    __tablename__ = "role_inclusions"

    role_id = Column(UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    included_role_id = Column(UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

    __table_args__ = (
        CheckConstraint("role_id != included_role_id", name="ck_no_self_inclusion"),
    )

    role = relationship("Role", foreign_keys=[role_id], back_populates="inclusions")
    included_role = relationship("Role", foreign_keys=[included_role_id], back_populates="included_by")


class RoleResourcePermission(Base):
    __tablename__ = "role_resource_permissions"

    role_id = Column(UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    resource_id = Column(UUID(as_uuid=False), ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True)
    permission_bits = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("permission_bits > 0", name="ck_permission_bits_positive"),
    )

    role = relationship("Role", back_populates="permissions")
    resource = relationship("Resource", back_populates="permissions")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")


class OrgExchange(Base):
    __tablename__ = "org_exchanges"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_a_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    org_b_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("org_a_id", "org_b_id", name="uq_exchange_pair"),
        CheckConstraint("org_a_id < org_b_id", name="ck_exchange_ordered_pair"),
        CheckConstraint("org_a_id != org_b_id", name="ck_exchange_different_orgs"),
    )

    org_a = relationship("Organization", foreign_keys=[org_a_id])
    org_b = relationship("Organization", foreign_keys=[org_b_id])
    exposed_roles = relationship("ExchangeRole", back_populates="exchange", cascade="all, delete-orphan")


class ExchangeRole(Base):
    __tablename__ = "exchange_roles"

    exchange_id = Column(UUID(as_uuid=False), ForeignKey("org_exchanges.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

    exchange = relationship("OrgExchange", back_populates="exposed_roles")
    role = relationship("Role")

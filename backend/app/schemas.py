from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Organizations ─────────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None


class OrgOut(BaseModel):
    id: str
    name: str
    parent_id: Optional[str]

    model_config = {"from_attributes": True}


# ── Users ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    org_id: str
    is_superadmin: bool = False
    is_org_admin: bool = False


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    org_id: Optional[str] = None
    is_superadmin: Optional[bool] = None
    is_org_admin: Optional[bool] = None


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    org_id: str
    is_superadmin: bool
    is_org_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Resources ─────────────────────────────────────────────────────────────────

class ResourceCreate(BaseModel):
    name: str
    resource_type: Literal["document", "video"]
    org_id: str


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    resource_type: Optional[Literal["document", "video"]] = None
    org_id: Optional[str] = None


class ResourceOut(BaseModel):
    id: str
    name: str
    resource_type: str
    org_id: str

    model_config = {"from_attributes": True}


# ── Roles ─────────────────────────────────────────────────────────────────────

class RoleCreate(BaseModel):
    name: str
    org_id: str


class RoleUpdate(BaseModel):
    name: str


class RoleOut(BaseModel):
    id: str
    name: str
    org_id: str

    model_config = {"from_attributes": True}


class InclusionCreate(BaseModel):
    included_role_id: str


class ParentRoleAdd(BaseModel):
    parent_role_id: str


class PermissionSet(BaseModel):
    permission_bits: int

    @field_validator("permission_bits")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("permission_bits must be > 0")
        return v


class PermissionOut(BaseModel):
    role_id: str
    resource_id: str
    permission_bits: int

    model_config = {"from_attributes": True}


# ── Resolve ───────────────────────────────────────────────────────────────────

class EffectivePermission(BaseModel):
    resource_id: str
    resource_name: str
    resource_type: str
    permission_bits: int
    permission_labels: list[str]


class ResolveResponse(BaseModel):
    user_id: str
    permissions: list[EffectivePermission]

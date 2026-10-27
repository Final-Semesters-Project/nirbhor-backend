from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Literal


class CreateAdminSchema(BaseModel):
   """Super admin creates a new regular admin account."""
   phone: str = Field(
      ...,
      description="Phone number must start with 01[3-9] (BD only)"
   )
   password: str
   name_en: str
   name_bn: str

   @field_validator("phone")
   @classmethod
   def validate_phone(cls, v: str) -> str:
      if not v.startswith("01") or len(v) != 11 or not v.isdigit():
         raise ValueError("Phone must be an 11-digit BD number starting with 01.")
      return v


class AdminListItem(BaseModel):
   user_id: UUID
   name: str
   phone: str
   role: str
   is_active: bool
   created_at: datetime
   last_active_at: datetime | None

   model_config = ConfigDict(from_attributes=True)


class AuditLogItem(BaseModel):
   log_id: UUID
   admin_name: str
   admin_role: str
   action: str
   target_user_id: UUID | None
   target_user_name: str | None
   details: str | None
   performed_at: datetime

   model_config = ConfigDict(from_attributes=True)
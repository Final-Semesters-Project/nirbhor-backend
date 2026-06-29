from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Literal

from app.models.provider_profile_model import VerificationStatus
from app.models.user_report_model import ReportStatus


# ── Dashboard ──────────────────────────────────────────────────────────────────

class AdminDashboardResponse(BaseModel):
    total_users: int
    total_providers: int
    total_seekers: int
    total_bookings: int
    pending_verifications: int
    pending_reports: int
    active_providers_today: int     # last_active_at within 24 hours


# ── Verifications ──────────────────────────────────────────────────────────────

class VerificationListItem(BaseModel):
    user_id: UUID
    name: str
    phone: str
    photo_url: str | None
    nid_front_url: str | None
    nid_back_url: str | None
    verification_level: str
    verification_status: str
    submitted_at: datetime          # created_at of the provider_profile

    model_config = ConfigDict(from_attributes=True)


class VerificationActionSchema(BaseModel):
    """Admin approves or rejects a provider's verification request."""
    verification_status: VerificationStatus
    rejection_reason: str | None = None


class VerificationActionResponse(BaseModel):
    user_id: UUID
    verification_status: str
    verification_level: str
    message: str


# ── Reports ────────────────────────────────────────────────────────────────────

class ReportListItem(BaseModel):
    report_id: UUID
    reporter_name: str
    reported_user_name: str
    reported_user_role: str
    reason: str
    status: ReportStatus
    booking_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportActionSchema(BaseModel):
    status: ReportStatus


class ReportActionResponse(BaseModel):
    report_id: UUID
    status: ReportStatus
    affected_user_id: UUID | None = None


# ── Users ──────────────────────────────────────────────────────────────────────

class AdminUserListItem(BaseModel):
    user_id: UUID
    name: str
    phone: str
    role: str
    is_active: bool
    last_active_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserDetail(AdminUserListItem):
    """Extended detail for single user view."""
    total_bookings: int
    average_rating: float | None    # providers only
    verification_level: str | None  # providers only
    verification_status: str | None  # providers only


# ── Analytics ──────────────────────────────────────────────────────────────────

class WeeklyBookingPoint(BaseModel):
    week_start: datetime
    count: int


class AdminAnalyticsResponse(BaseModel):
    total_users: int
    total_bookings: int
    average_provider_rating: float | None
    active_providers_count: int         # active in last 30 days
    seeker_count: int
    provider_count: int
    seeker_to_provider_ratio: float | None
    bookings_per_week: list[WeeklyBookingPoint]

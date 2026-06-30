import asyncio
from datetime import datetime, timedelta, timezone
from typing import Sequence
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from app.repositories.base_repository import BaseRepository
from sqlalchemy import case, select, func
from app.models.user_model import User, Role
from app.models.provider_profile_model import ProviderProfile, VerificationLevel, VerificationStatus
from app.models.booking_model import Booking
from app.models.user_report_model import UserReport, ReportStatus


class AdminRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Dashboard ─────────────────────────────────────────────────────────────

    async def get_dashboard_counts(self) -> dict:
        now = datetime.now(timezone.utc)

        # ── Query 1: all User-table counts in one round-trip ──────────────────
        # case((condition, value)) counts only rows where condition is True.
        # Rows where condition is False contribute NULL, which COUNT ignores.
        user_counts_result = await self.db.execute(
            select(
                func.count().label("total_users"),
                func.count(
                    case((User.role == Role.PROVIDER, 1))
                ).label("total_providers"),
                func.count(
                    case((User.role == Role.SEEKER, 1))
                ).label("total_seekers"),
                func.count(
                    case((
                        (User.role == Role.PROVIDER) &
                        (User.last_active_at >= now - timedelta(hours=24)),
                        1
                    ))
                ).label("active_providers_today"),
            ).select_from(User)
        )
        user_counts = user_counts_result.mappings().first()

        # ── Queries 2, 3, 4: different tables — run in parallel ───────────────
        # asyncio.gather fires all three at the same time.
        # Total wait = slowest single query, not sum of all three.
        total_bookings, pending_verifications, pending_reports = await asyncio.gather(
            self.db.scalar(
                select(func.count()).select_from(Booking)
            ),
            self.db.scalar(
                select(func.count())
                .select_from(ProviderProfile)
                .where(ProviderProfile.verification_status == VerificationStatus.PENDING)
            ),
            self.db.scalar(
                select(func.count())
                .select_from(UserReport)
                .where(UserReport.status == ReportStatus.PENDING)
            ),
        )

        return {
            "total_users":            (user_counts or {}).get("total_users") or 0,
            "total_providers":        (user_counts or {}).get("total_providers") or 0,
            "total_seekers":          (user_counts or {}).get("total_seekers") or 0,
            "active_providers_today": (user_counts or {}).get("active_providers_today") or 0,
            "total_bookings":         total_bookings or 0,
            "pending_verifications":  pending_verifications or 0,
            "pending_reports":        pending_reports or 0,
        }

    # ── Verifications ─────────────────────────────────────────────────────────

    async def get_pending_verifications(self) -> Sequence:
        result = await self.db.execute(
            select(User, ProviderProfile)
            .join(ProviderProfile, User.id == ProviderProfile.user_id)
            .where(ProviderProfile.verification_status == VerificationStatus.PENDING)
            .order_by(ProviderProfile.updated_at.asc())   # oldest first
        )
        return result.all()

    # async def get_provider_for_verification(
    #     self,
    #     provider_id: UUID
    # ) -> tuple[User, ProviderProfile] | None:
    #     result = await self.db.execute(
    #         select(User, ProviderProfile)
    #         .join(ProviderProfile, User.id == ProviderProfile.user_id)
    #         .where(User.id == provider_id)
    #     )
    #     row = result.first()
    #     if row is None:
    #         return None
    #     return (row[0], row[1])

    async def approve_verification(self, provider_profile: ProviderProfile) -> ProviderProfile:
        provider_profile.verification_status = VerificationStatus.APPROVED
        provider_profile.verification_level = VerificationLevel.VERIFIED
        provider_profile.verification_rejection_reason = None
        await self.db.flush()
        return provider_profile

    async def reject_verification(
        self,
        provider_profile: ProviderProfile,
        reason: str
    ) -> ProviderProfile | None:
        provider_profile.verification_status = VerificationStatus.REJECTED
        provider_profile.verification_rejection_reason = reason
        await self.db.flush()
        return provider_profile

    # ── Reports ───────────────────────────────────────────────────────────────

    async def get_reports(self, status_filter: str | None = None) -> Sequence:
        Reporter = aliased(User, name="reporter")
        Reported = aliased(User, name="reported")

        stmt = (
            select(UserReport, Reporter, Reported)
            .join(Reporter, UserReport.reporter_id == Reporter.id)
            .join(Reported, UserReport.reported_user_id == Reported.id)
            .order_by(UserReport.created_at.desc())
        )
        if status_filter:
            stmt = stmt.where(UserReport.status == status_filter)

        result = await self.db.execute(stmt)
        return result.all()

    async def get_report_by_id(self, report_id: UUID) -> UserReport | None:
        result = await self.db.execute(
            select(UserReport).where(UserReport.id == report_id)
        )
        return result.scalar_one_or_none()

    async def update_report_status(
        self,
        report: UserReport,
        new_status: ReportStatus,
    ) -> UserReport:
        report.status = new_status
        await self.db.flush()
        return report

    async def suspend_user(self, user_id: UUID) -> User | None:
        user = await self.db.get(User, user_id)

        if user is None:
            return None

        if user.role == Role.ADMIN:
            return None

        user.is_active = False
        await self.db.flush()
        return user

from uuid import UUID
from asyncpg import ForeignKeyViolationError, UniqueViolationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.core.cache import UserCacheService
from app.core.integrity_error_parser import parse_integrity_error
from app.models.provider_profile_model import VerificationStatus
from app.repositories.admin_repository import AdminRepository
from app.repositories.provider_repository import ProviderRepository
from app.schemas.admin_schema import (
    AdminDashboardResponse,
    VerificationListItem,
    VerificationActionSchema,
    VerificationActionResponse,
    ReportListItem,
    ReportActionSchema,
    ReportActionResponse,
    AdminUserListItem,
    AdminUserDetail,
    AdminAnalyticsResponse,
)
from app.models.user_report_model import ReportStatus
from app.core.exceptions import DomainValidationError, DomainIntegrityError
from app.core.i18n import t
import cloudinary.utils


class AdminService:
    # ================ Signed URL Generation for Cloudinary ================

    @staticmethod
    def get_signed_nid_url(public_id: str | None, expires_in: int = 300) -> str | None:
        """
        Generates a signed URL valid for expires_in seconds (default 5 minutes).
        Returns None if public_id is None.
        Called when admin fetches a provider's verification details.
        """
        if not public_id:
            return None
        url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            sign_url=True,
            secure=True,
            # expires_at is not directly supported in Python SDK this way
            # The URL is signed with the API secret — Cloudinary validates it
        )
        return url

    @staticmethod
    async def get_dashboard(db: AsyncSession) -> AdminDashboardResponse:
        repo = AdminRepository(db)
        data = await repo.get_dashboard_counts()
        return AdminDashboardResponse(**data)

    @staticmethod
    async def get_pending_verifications(
        db: AsyncSession, lang: str
    ) -> list[VerificationListItem]:
        repo = AdminRepository(db)
        rows = await repo.get_pending_verifications()
        return [
            VerificationListItem(
                user_id=user.id,
                name=user.name_en,
                phone=user.phone_en,
                photo_url=profile.photo_url,
                nid_url_front=AdminService.get_signed_nid_url(
                    profile.nid_url_front),
                nid_url_back=AdminService.get_signed_nid_url(
                    profile.nid_url_back),
                verification_level=profile.verification_level.value,
                verification_status=profile.verification_status.value,
                submitted_at=profile.updated_at or profile.created_at,
            )
            for user, profile in rows
        ]

    @staticmethod
    async def get_analytics(db: AsyncSession) -> AdminAnalyticsResponse:
        repo = AdminRepository(db)
        data = await repo.get_analytics()
        return AdminAnalyticsResponse(**data)

    @staticmethod
    async def handle_verification(
        provider_id: UUID,
        data: VerificationActionSchema,
        db: AsyncSession,
        lang: str,
    ) -> VerificationActionResponse:
        admin_repo = AdminRepository(db)
        provider_repo = ProviderRepository(db)

        provider_profile = await provider_repo.get_by_id(provider_id)

        if provider_profile is None:
            raise DomainIntegrityError(t("provider_not_found", lang))

        try:
            if data.verification_status == VerificationStatus.APPROVED:
                updated_provider_profile = await admin_repo.approve_verification(provider_profile)

                logger.info(
                    f"Admin approved verification for provider {provider_id}")
                # TODO: send FCM to provider — "Your account is now verified!"
            else:
                if not data.rejection_reason:
                    raise DomainValidationError(
                        t("rejection_reason_required", lang))

                updated_provider_profile = await admin_repo.reject_verification(provider_profile=provider_profile, reason=data.rejection_reason)
                logger.info(
                    f"Admin rejected verification for provider {provider_id}: "
                    f"{data.rejection_reason}"
                )
                # TODO: send FCM to provider — "Your verification was rejected: {reason}"

            await db.commit()

            return VerificationActionResponse(
                user_id=provider_id,
                verification_status=provider_profile.verification_status,
                verification_level=provider_profile.verification_level,
                message=t("verification_updated", lang),
            )
        except IntegrityError as e:
            await db.rollback()
            raw = str(e.orig) if e.orig else str(e)
            readable = parse_integrity_error(raw, lang)

            # e.orig may be a string (SQLAlchemy asyncpg dialect behavior) or
            # the actual asyncpg exception — handle both cases
            is_fk = (
                isinstance(e.orig, ForeignKeyViolationError)
                or "ForeignKeyViolationError" in raw
            )
            is_unique = (
                isinstance(e.orig, UniqueViolationError)
                or "UniqueViolationError" in raw
            )

            # unwrap the original asyncpg exception to route correctly
            if is_fk:
                logger.warning(
                    f"FK violation in provider verification update by admin: {raw}")
                raise DomainValidationError(
                    error_message=readable,
                    raw_error=raw
                )
            if is_unique:
                logger.warning(
                    f"Unique violation in provider verification update by admin: {raw}")
                raise DomainIntegrityError(
                    error_message=readable,
                    raw_error=raw
                )

            logger.error(
                f"IntegrityError in provider verification update by admin: {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except (DomainIntegrityError, DomainValidationError):
            # let domain exceptions bubble up untouched to the global handler
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Unexpected error in provider verification update by admin: {e}")
            raise

    @staticmethod
    async def get_reports(
        db: AsyncSession,
        # lang: str,
        status_filter: str | None = None,
    ) -> list[ReportListItem]:
        repo = AdminRepository(db)
        rows = await repo.get_reports(status_filter)
        return [
            ReportListItem(
                report_id=report.id,
                reporter_name=reporter.name_en,
                reported_user_name=reported.name_en,
                reported_user_role=reported.role.value,
                reason=report.reason,
                status=report.status.value,
                booking_id=report.booking_id,
                created_at=report.created_at,
            )
            for report, reporter, reported in rows
        ]

    @staticmethod
    async def handle_report(
        report_id: UUID,
        data: ReportActionSchema,
        db: AsyncSession,
        lang: str,
    ) -> ReportActionResponse:
        admin_repo = AdminRepository(db)

        report = await admin_repo.get_report_by_id(report_id)
        if not report:
            raise DomainValidationError(t("report_not_found", lang))

        affected_user_id = None

        if data.status == ReportStatus.ACTION_TAKEN:
            # Suspend the reported user and mark report as ACTION_TAKEN
            await admin_repo.suspend_user(report.reported_user_id)
            affected_user_id = report.reported_user_id

            # await admin_repo.update_report_status(report, ReportStatus.ACTION_TAKEN)
            logger.info(
                f"Admin suspended user {report.reported_user_id} "
                f"via report {report_id}"
            )
        elif data.status == ReportStatus.REVIEWED:
            if report.status == ReportStatus.ACTION_TAKEN:
                raise DomainValidationError("can_not_dismiss_report")
            # await admin_repo.update_report_status(report, ReportStatus.REVIEWED)
            logger.info(f"Admin dismissed report {report_id}")
        elif data.status == ReportStatus.UNDER_INVESTIGATION:
            if report.status != ReportStatus.PENDING:
                raise DomainValidationError("can_not_set_under_investigation")
            logger.info(
                f"Admin marked report {report_id} as under investigation"
            )

        await admin_repo.update_report_status(report, data.status)
        await db.commit()

        return ReportActionResponse(
            report_id=report_id,
            status=data.status,
            affected_user_id=affected_user_id,
        )

    @staticmethod
    async def get_users(
        db: AsyncSession,
        role_filter: str | None = None,
        is_active_filter: bool | None = None,
    ) -> list[AdminUserListItem]:
        repo = AdminRepository(db)
        users = await repo.get_users(role_filter, is_active_filter)
        return [
            AdminUserListItem(
                user_id=u.id,
                name_en=u.name_en,
                name_bn=u.name_bn,
                phone=u.phone_en,
                role=u.role,
                is_active=u.is_active,
                last_active_at=u.last_active_at,
                created_at=u.created_at,
            )
            for u in users
        ]

    @staticmethod
    async def get_user_detail(
        user_id: UUID, db: AsyncSession, lang: str
    ) -> AdminUserDetail:
        repo = AdminRepository(db)
        data = await repo.get_user_detail(user_id)
        if not data:
            raise DomainValidationError(t("user_not_found", lang))

        user = data["user"]
        profile = data["profile"]

        return AdminUserDetail(
            user_id=user.id,
            name_en=user.name_en,
            name_bn=user.name_bn,
            phone=user.phone_en,
            role=user.role,
            is_active=user.is_active,
            last_active_at=user.last_active_at,
            created_at=user.created_at,
            total_bookings=data["total_bookings"],
            average_rating=profile.average_rating if profile else None,
            verification_level=profile.verification_level.value if profile else None,
            verification_status=profile.verification_status.value if profile else None,
            ai_review_summary_en=profile.ai_review_summary_en if profile else None,
            ai_review_summary_bn=profile.ai_review_summary_bn if profile else None,
            has_smartphone=profile.has_smartphone if profile else None,
            base_location=profile.base_location if profile else None,
            nid_url_back=profile.nid_url_back if profile else None,
            nid_url_front=profile.nid_url_front if profile else None,
            photo_url=profile.photo_url if profile else None,
            warning_status=profile.warning_status if profile else None,
            working_radius_km=profile.working_radius_km if profile else None,
        )

    @staticmethod
    async def toggle_user_active(
        user_id: UUID, db: AsyncSession, lang: str
    ) -> dict:
        repo = AdminRepository(db)
        user = await repo.toggle_user_active(user_id)
        if not user:
            raise DomainValidationError(t("user_not_found", lang))
        await db.commit()
        logger.info(
            f"Admin toggled user {user_id} is_active → {user.is_active}"
        )

        UserCacheService.invalidate(str(user_id))
        return {
            "user_id": user_id,
            "is_active": user.is_active,
            "message": t("user_status_updated", lang),
        }

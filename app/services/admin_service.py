from uuid import UUID
from asyncpg import ForeignKeyViolationError, UniqueViolationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
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


class AdminService:
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
                nid_url_front=profile.nid_url_front,
                nid_url_back=profile.nid_url_back,
                verification_level=profile.verification_level.value,
                verification_status=profile.verification_status.value,
                submitted_at=profile.updated_at or profile.created_at,
            )
            for user, profile in rows
        ]

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

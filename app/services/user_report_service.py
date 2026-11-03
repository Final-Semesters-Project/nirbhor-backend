

class ReviewService:
    pass
from uuid import UUID

from asyncpg import ForeignKeyViolationError
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t
from app.core.integrity_error_parser import parse_integrity_error
from app.core.paginator import paginate
from app.models.user_report_model import UserReport
from app.repositories.user_report_repository import UserReportRepository
from app.schemas.pagination_schema import PageResponse
from app.schemas.user_report_schema import (
    CreateUserReportSchema,
    UserReportListItem,
    UserReportResponse,
)


class UserReportService:

    @staticmethod
    async def create_report(
        data: CreateUserReportSchema,
        reporter_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> UserReportResponse:
        report_repo = UserReportRepository(db)

        if data.reported_user_id == reporter_id:
            raise DomainValidationError(t("can_not_report_yourself", lang))

        reported_user = await report_repo.get_reported_user(
            data.reported_user_id
        )
        if reported_user is None:
            raise DomainValidationError(t("reported_user_not_found", lang))

        if data.booking_id is not None:
            booking = await report_repo.get_booking(data.booking_id)
            if booking is None:
                raise DomainValidationError(t("booking_not_found", lang))

            booking_party_ids = {booking.seeker_id, booking.provider_id}
            if reporter_id not in booking_party_ids:
                raise DomainValidationError(t("booking_not_yours", lang))

            if data.reported_user_id not in booking_party_ids:
                raise DomainValidationError(t("reported_user_not_found", lang))

            if {
                reporter_id,
                data.reported_user_id,
            } != booking_party_ids:
                raise DomainValidationError(t("booking_not_yours", lang))

        try:
            report = await report_repo.create_report(
                reporter_id=reporter_id,
                reported_user_id=data.reported_user_id,
                booking_id=data.booking_id,
                reason=data.reason,
            )
            await db.commit()

            logger.info(
                f"User report created: {report.id} "
                f"by {reporter_id} against {data.reported_user_id}"
            )

            return UserReportResponse(
                report_id=report.id,
                reported_user_id=report.reported_user_id,
                booking_id=report.booking_id,
                reason=report.reason,
                status=report.status,
                created_at=report.created_at,
            )
        except IntegrityError as e:
            await db.rollback()
            raw = str(e.orig) if e.orig else str(e)
            readable = parse_integrity_error(raw, lang)
            if isinstance(e.orig, ForeignKeyViolationError) or "ForeignKeyViolationError" in raw:
                raise DomainValidationError(
                    error_message=readable,
                    raw_error=raw,
                )
            raise DomainIntegrityError(
                error_message=readable,
                raw_error=raw,
            )
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def get_current_user_reports(
        reporter_id: UUID,
        db: AsyncSession,
        lang: str,
        page: int = 1,
        page_size: int = 20,
    ) -> PageResponse[UserReportListItem]:
        report_repo = UserReportRepository(db)

        def transform(report: UserReport) -> UserReportListItem:
            return UserReportListItem(
                report_id=report.id,
                reported_user_id=report.reported_user_id,
                booking_id=report.booking_id,
                reason=report.reason,
                status=report.status,
                created_at=report.created_at,
            )

        return await paginate(
            db=db,
            stmt=report_repo.get_reports_by_reporter_stmt(reporter_id),
            pk_col=UserReport.id,
            page=page,
            page_size=page_size,
            transformer=transform,
        )

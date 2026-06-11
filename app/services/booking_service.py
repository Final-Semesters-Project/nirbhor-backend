from uuid import UUID
from datetime import datetime, timezone
from asyncpg import ForeignKeyViolationError, UniqueViolationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.core.integrity_error_parser import parse_integrity_error
from app.models.booking_model import BookingStatus
from app.models.provider_profile_model import ProviderProfile
from app.repositories.booking_repository import BookingRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.user_repository import UserRepository
from app.schemas.booking_schema import BookingInitiateSchema, BookingRespondFromNotificationSchema, BookingInitiateResponse, BookingListItem
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t


# Business rule: max 10 open (INITIATED) booking at a time per seeker
MAX_OPEN_BOOKINGS = 10          # max simultaneous unlocked numbers
FOLLOWUP_DELAY_HOURS = 2        # FCM fires after this many hours


class BookingService:
    @staticmethod
    async def initiate_booking(
        data: BookingInitiateSchema,
        seeker_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> BookingInitiateResponse:
        """
        Seeker clicks "Request to Call" on a provider's profile. 
        This creates a new booking record and returns the phone number of the provider so the frontend can trigger the native dialer.
        """

        booking_repo = BookingRepository(db)
        user_repo = UserRepository(db)
        skill_repo = SkillRepository(db)

        # 1. Spam guard: seeker must not have another open booking
        open_count = await booking_repo.count_active_initiated(seeker_id)
        if open_count >= MAX_OPEN_BOOKINGS:
            raise DomainIntegrityError(t("too_many_open_bookings", lang))

        # 2. Provider must exist and be available
        provider = await user_repo.get_by_id(data.provider_id)
        if not provider or not provider.is_active:
            raise DomainValidationError(t("provider_unavailable", lang))

        provider_profile = await db.get(ProviderProfile, data.provider_id)
        if not provider_profile or not provider_profile.is_available:
            raise DomainValidationError(t("provider_unavailable", lang))

        # skill_id must be assigned to provider
        is_provider_skilled = await skill_repo.check_if_provider_has_skill(
            skill_id=data.skill_id,
            provider_id=data.provider_id
        )

        if not is_provider_skilled:
            raise DomainValidationError(t("provider_unskilled", lang))

        try:
            # 3. Create the booking
            booking = await booking_repo.create_booking(
                seeker_id=seeker_id,
                provider_id=data.provider_id,
                skill_id=data.skill_id,  # for which job the booking was initiated
                latitude=data.latitude,
                longitude=data.longitude,
            )

            await db.commit()

            logger.success(
                f"Booking initiated: {booking.id} by seeker {seeker_id}")

            # TODO: 4. Schedule the FCM follow-up notification (stub — implement with APScheduler)
            # NotificationService.schedule_booking_followup(booking.id, delay_hours=2)

            # Dynamically select the localized name variant
            localized_name = provider.name_bn if lang == "bn" else provider.name_en
            return BookingInitiateResponse(
                booking_id=booking.id,
                # send the phone in response, so no additional queries needs to be made
                provider_phone=provider.phone_en,
                provider_name=localized_name,
                status=booking.status,
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
                    f"FK violation in initiate booking: {raw}")
                raise DomainValidationError(
                    error_message=readable,
                    raw_error=raw
                )
            if is_unique:
                logger.warning(
                    f"Unique violation in initiate booking: {raw}")
                raise DomainIntegrityError(
                    error_message=readable,
                    raw_error=raw
                )

            logger.error(f"IntegrityError in initiate booking: {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except (DomainIntegrityError, DomainValidationError):
            # let domain exceptions bubble up untouched to the global handler
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error in initiate booking: {e}")
            raise

    @staticmethod
    async def respond_to_booking(
        booking_id: UUID,
        data: BookingRespondFromNotificationSchema,
        seeker_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> dict:
        """
        Seeker confirms or cancels a booking from the FCM notification.
        hired=True  → status becomes IN_PROGRESS, confirmed_at is set
        hired=False → status becomes CANCELLED
        """
        booking_repo = BookingRepository(db)
        user_repo = UserRepository(db)

        booking = await booking_repo.get_by_id_with_parties(booking_id)

        if not booking:
            raise DomainValidationError(t("booking_not_found", lang))

        # Only the seeker who created this booking can respond
        if booking.seeker_id != seeker_id:
            raise DomainValidationError(t("booking_not_yours", lang))

        # Can only respond to INITIATED bookings
        if booking.status != BookingStatus.INITIATED:
            raise DomainValidationError(t("booking_wrong_status", lang))

        if data.hired:
            booking.status = BookingStatus.IN_PROGRESS
            booking.confirmed_at = datetime.now(timezone.utc)
            booking.work_schedule = data.work_schedule

        try:
            # Auto-cancel all other INITIATED bookings from this seeker
            cancelled_count = await booking_repo.cancel_other_initiated(
                seeker_id=seeker_id,
                exclude_booking_id=booking_id,
            )
            if cancelled_count > 0:
                logger.info(
                    f"Auto-cancelled {cancelled_count} other INITIATED bookings "
                    f"for seeker {seeker_id} after confirming booking {booking_id}"
                )

                # Implied Activity: bump last_active_at for both parties
                now = datetime.now(timezone.utc)
                await user_repo.update_last_active(booking.seeker_id, now)
                await user_repo.update_last_active(booking.provider_id, now)

                logger.info(
                    f"Booking {booking_id} → IN_PROGRESS by seeker {seeker_id}")
            else:
                booking.status = BookingStatus.CANCELLED
                logger.info(
                    f"Booking {booking_id} → CANCELLED by seeker {seeker_id}")

            await db.commit()
            return {"booking_id": booking_id, "status": booking.status}
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
                    f"FK violation in booking status update(FCM): {raw}")
                raise DomainValidationError(
                    error_message=readable,
                    raw_error=raw
                )
            if is_unique:
                logger.warning(
                    f"Unique violation in booking status update(FCM): {raw}")
                raise DomainIntegrityError(
                    error_message=readable,
                    raw_error=raw
                )

            logger.error(
                f"IntegrityError in booking status update(FCM): {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except (DomainIntegrityError, DomainValidationError):
            # let domain exceptions bubble up untouched to the global handler
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Unexpected error in booking status update(FCM): {e}")
            raise

    @staticmethod
    async def get_provider_incoming(
        provider_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> list[BookingListItem]:
        """Provider's 'Incoming Bookings' tab — only IN_PROGRESS bookings will be shown."""
        booking_repo = BookingRepository(db)
        bookings_with_seekers = await booking_repo.get_provider_incoming_with_seekers(provider_id)

        result = []
        for booking, seeker in bookings_with_seekers:
            localized_name = seeker.name_bn if lang == "bn" else seeker.name_en
            localized_skill_name = booking.skill.name_bn if lang == "bn" else booking.skill.name_en
            logger.success(dict(result))
            result.append(BookingListItem(
                booking_id=booking.id,
                status=booking.status,
                skill_id=booking.skill_id,
                skill_name=localized_skill_name,
                created_at=booking.created_at,
                work_schedule=booking.work_schedule,
                other_party_name=localized_name,
                other_party_phone=seeker.phone_en,
            ))
        return result

    @staticmethod
    async def get_seeker_history(
        seeker_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> list[BookingListItem]:
        """Seeker's full booking history including INITIATED entries."""
        booking_repo = BookingRepository(db)
        bookings_with_providers = await booking_repo.get_seeker_history_with_providers(seeker_id)

        result = []
        for booking, provider in bookings_with_providers:
            localized_name = provider.name_bn if lang == "bn" else provider.name_en
            localized_skill_name = booking.skill.name_bn if lang == "bn" else booking.skill.name_en
            phone = provider.phone_en

            result.append(BookingListItem(
                booking_id=booking.id,
                status=booking.status,
                skill_id=booking.skill_id,
                skill_name=localized_skill_name,
                created_at=booking.created_at,
                work_schedule=booking.work_schedule,
                other_party_name=localized_name,
                other_party_phone=phone,
            ))
        return result

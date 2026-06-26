from typing import cast
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
from app.schemas.booking_schema import BookingDetailsForLastInitiatedActiveBooking, BookingInitiateSchema, BookingRespondFromNotificationSchema, BookingInitiateResponse, BookingListItem, LastInitiatedActiveBookingSchema, SingleBookingDetailResponse
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t


# Business rule: max 10 open (INITIATED) booking at a time per seeker
MAX_OPEN_BOOKINGS = 1          # max simultaneous unlocked numbers
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
        # changed max open bookings from 10 to 1
        if open_count > MAX_OPEN_BOOKINGS:
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
    async def get_single_booking(
        booking_id: UUID,
        current_user_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> SingleBookingDetailResponse:
        from geoalchemy2.shape import to_shape
        from shapely.geometry import Point

        booking_repo = BookingRepository(db)
        user_repo = UserRepository(db)

        booking = await booking_repo.get_single_booking(booking_id)
        if not booking:
            raise DomainValidationError(t("booking_not_found", lang))

        # Only the seeker or provider of this booking can view it
        if booking.seeker_id != current_user_id and booking.provider_id != current_user_id:
            raise DomainValidationError(t("booking_not_yours", lang))

        is_seeker = booking.seeker_id == current_user_id

        if is_seeker:
            other = await user_repo.get_by_id(booking.provider_id)
        else:
            other = await user_repo.get_by_id(booking.seeker_id)

        # Extract job location coordinates from PostGIS point
        lat, lng = None, None
        if booking.job_location is not None:
            point = cast(Point, to_shape(booking.job_location))
            lng = point.x
            lat = point.y

        return SingleBookingDetailResponse(
            booking_id=booking.id,
            status=booking.status,
            skill_id=booking.skill_id,
            created_at=booking.created_at,
            call_unlocked_at=booking.call_unlocked_at,
            confirmed_at=booking.confirmed_at,
            work_schedule=booking.work_schedule,
            completed_at=booking.completed_at,
            other_party_name=(
                other.name_bn if lang == "bn" and other else other.name_en) if other else "-",
            # Phone visible to seeker always (they unlocked it).
            # Provider sees seeker phone only when IN_PROGRESS (they need to go there).
            other_party_phone=other.phone_en if other else None,
            job_latitude=lat,
            job_longitude=lng,
        )

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
            raise DomainValidationError(t("can_not_update_booking", lang))

        # Can only respond to INITIATED bookings
        if booking.status != BookingStatus.INITIATED:
            raise DomainValidationError(t("booking_wrong_status", lang))

        if data.hired:
            booking.status = BookingStatus.IN_PROGRESS
            booking.confirmed_at = datetime.now(timezone.utc)
            booking.work_schedule = data.work_schedule
        else:
            booking.status = BookingStatus.CANCELLED

        try:
            # If they hired the provider, update active tracking parameters
            if data.hired:
                logger.info(
                    f"Booking {booking_id} → IN_PROGRESS by seeker {seeker_id}")

                # Implied Activity: bump last_active_at for both parties
                now = datetime.now(timezone.utc)
                await user_repo.update_last_active(booking.seeker_id, now)
                await user_repo.update_last_active(booking.provider_id, now)

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
            else:
                # booking.status = BookingStatus.CANCELLED
                logger.info(
                    f"Booking manually {booking_id} → CANCELLED by seeker {seeker_id}")

            await db.commit()

            msg = "IN_PROGRESS" if data.hired else "CANCELLED"
            logger.success(f"Booking status updated to {msg}")

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
        logger.info(f"bookings_with_seekers: {bookings_with_seekers}")
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
    async def get_providers_completed_bookings(
        provider_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> list[BookingListItem]:
        """Provider's 'Completed Bookings/Jobs tab — only COMPLETED bookings will be shown with options to give review."""
        booking_repo = BookingRepository(db)
        bookings_with_seekers = await booking_repo.get_provider_completed_with_seekers(provider_id)

        result = []
        logger.info(
            f"completed bookings with seekers: {bookings_with_seekers}")
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
    async def get_seeker_last_active_initiated(
        seeker_id: UUID,
        db: AsyncSession,
        lang: str
    ) -> LastInitiatedActiveBookingSchema:
        booking_repo = BookingRepository(db)
        user_repo = UserRepository(db)

        booking = await booking_repo.get_active_initiated_booking(seeker_id=seeker_id)

        if not booking:
            return LastInitiatedActiveBookingSchema(has_active_booking=False, booking=None)

        provider = await user_repo.get_by_id(id=booking.provider_id)

        if not provider:
            return LastInitiatedActiveBookingSchema(has_active_booking=False, booking=None)

        localized_name = provider.name_bn if lang == "bn" else provider.name_en

        return (
            LastInitiatedActiveBookingSchema(
                has_active_booking=True,
                booking=BookingDetailsForLastInitiatedActiveBooking(
                    booking_id=booking.id,
                    provider_name=localized_name,
                    provider_phone=provider.phone_en,
                    created_at=booking.created_at,
                    status=booking.status
                )
            )
        )

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

    @staticmethod
    async def mark_completed(
        booking_id: UUID,
        seeker_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> dict:
        booking_repo = BookingRepository(db)

        booking = await booking_repo.get_single_booking(booking_id)
        if not booking:
            raise DomainValidationError(t("booking_not_found", lang))

        if booking.seeker_id != seeker_id:
            raise DomainValidationError(t("booking_not_yours", lang))

        if booking.status != BookingStatus.IN_PROGRESS:
            raise DomainValidationError(t("booking_wrong_status", lang))

        updated = await booking_repo.mark_completed(booking)
        await db.commit()

        logger.info(
            f"Booking {booking_id} marked COMPLETED by seeker {seeker_id}")
        return {"booking_id": booking_id, "status": updated.status}

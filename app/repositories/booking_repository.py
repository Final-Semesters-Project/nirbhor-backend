from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy.orm import selectinload
from app.models.booking_model import Booking, BookingStatus
from app.models.user_model import User
from app.repositories.base_repository import BaseRepository


class BookingRepository(BaseRepository[Booking]):
    def __init__(self, db: AsyncSession):
        super().__init__(Booking, db)

    async def count_active_initiated(self, seeker_id: UUID) -> int:
        """
        Count INITIATED bookings from this seeker within the last 2 hours.
        We only count within 2 hours because that's when the first FCM fires.
        After 2 hours the seeker is done unlocking numbers for this session.
        """
        two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        result = await self.db.execute(
            select(func.count())
            .where(Booking.seeker_id == seeker_id)
            .where(Booking.status == BookingStatus.INITIATED)
            # within current session
            .where(Booking.call_unlocked_at >= two_hours_ago)
        )
        return result.scalar_one()

    async def cancel_other_initiated(
        self, seeker_id: UUID, exclude_booking_id: UUID
    ) -> int:
        """
        When seeker confirms hiring one provider from notification, 
        cancel all other open INITIATED bookings from this seeker(bulk update). Returns count of cancelled rows. This helps prevent spamming notifications after 12 hours.
        """
        from sqlalchemy import update
        result = await self.db.execute(
            update(Booking)
            .where(Booking.seeker_id == seeker_id)
            .where(Booking.status == BookingStatus.INITIATED)
            .where(Booking.id != exclude_booking_id)
            .values(status=BookingStatus.CANCELLED)
            .returning(Booking.id)  # lets us count how many were cancelled
        )
        return len(result.all())

    async def get_initiated_ready_for_followup(self) -> list["Booking"]:
        """
        Find INITIATED bookings that are exactly 2 hours old (±5 min window).
        Called by APScheduler every 5 minutes to fire the first FCM.
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=2, minutes=5)
        window_end = now - timedelta(hours=2)

        result = await self.db.execute(
            select(Booking)
            .where(Booking.status == BookingStatus.INITIATED)
            .where(Booking.call_unlocked_at >= window_start)
            .where(Booking.call_unlocked_at <= window_end)
        )
        return list(result.scalars().all())

    async def create_booking(
        self,
        seeker_id: UUID,
        provider_id: UUID,
        skill_id: int,
        latitude: float,
        longitude: float,
    ) -> Booking:
        """Insert a new INITIATED booking with job_location set."""
        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        booking = Booking(
            seeker_id=seeker_id,
            provider_id=provider_id,
            skill_id=skill_id,
            status=BookingStatus.INITIATED,
            call_unlocked_at=datetime.now(timezone.utc),
            job_location=point,
        )
        self.db.add(booking)
        await self.db.flush()  # get the generated ID without committing
        return booking

    async def get_by_id_with_parties(self, booking_id: UUID) -> Booking | None:
        """
        Load booking with seeker and provider eagerly joined.
        We join User twice using aliased() to avoid ambiguity.
        """
        from sqlalchemy.orm import aliased
        from sqlalchemy import select

        SeekerUser = aliased(User, name="seeker_user")
        ProviderUser = aliased(User, name="provider_user")

        result = await self.db.execute(
            select(Booking, SeekerUser, ProviderUser)
            .join(SeekerUser, Booking.seeker_id == SeekerUser.id)
            .join(ProviderUser, Booking.provider_id == ProviderUser.id)
            .where(Booking.id == booking_id)
        )
        row = result.first()
        if not row:
            return None
        booking, seeker, provider = row
        # Attach for easy access in service layer
        booking._seeker = seeker
        booking._provider = provider
        return booking

    async def get_provider_incoming(self, provider_id: UUID) -> list[Booking]:
        """Bookings where this provider has active work (IN_PROGRESS only => Incoming Bookings)."""
        result = await self.db.execute(
            select(Booking)
            .where(Booking.provider_id == provider_id)
            .where(Booking.status == BookingStatus.IN_PROGRESS)
            .order_by(Booking.confirmed_at.desc())
        )
        return list(result.scalars().all())

    async def get_provider_incoming_with_seekers(self, provider_id: UUID) -> list[tuple[Booking, User]]:
        """Bookings with seeker & skill eagerly loaded."""
        from sqlalchemy.orm import aliased

        result = await self.db.execute(
            select(Booking, User)
            .join(User, Booking.seeker_id == User.id)
            .options(selectinload(Booking.skill))
            .where(Booking.provider_id == provider_id)
            .where(Booking.status == BookingStatus.IN_PROGRESS)
            .order_by(Booking.confirmed_at.desc())
        )
        return list(result.tuples())

    async def get_seeker_history_with_providers(self, seeker_id: UUID) -> list[tuple[Booking, User]]:
        """Bookings with provider eagerly loaded."""
        result = await self.db.execute(
            select(Booking, User)
            .join(User, Booking.provider_id == User.id)
            .options(selectinload(Booking.skill))
            .where(Booking.seeker_id == seeker_id)
            .order_by(Booking.created_at.desc())
        )
        return list(result.tuples())

    async def get_seeker_history(self, seeker_id: UUID) -> list[Booking]:
        """All bookings for this seeker, newest first."""
        result = await self.db.execute(
            select(Booking)
            .where(Booking.seeker_id == seeker_id)
            .order_by(Booking.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_provider_history(self, provider_id: UUID) -> list[Booking]:
        """All bookings/jobs for this provider, newest first."""
        result = await self.db.execute(
            select(Booking)
            .where(Booking.provider_id == provider_id)
            .order_by(Booking.created_at.desc())
        )
        return list(result.scalars().all())

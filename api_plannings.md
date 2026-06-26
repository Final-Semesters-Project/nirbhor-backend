**Next batch (core app flows):**
- `GET /api/v1/providers/{provider_id}/public` — seeker taps provider card to see full profile
- `GET /api/v1/urgent/broadcast/{id}/status` — seeker polls to see if broadcast was claimed (or use FCM)

**After that (admin panel):**
- `GET /api/v1/admin/dashboard` — counts summary
- `GET /api/v1/admin/verifications` — pending verification list
- `PATCH /api/v1/admin/verifications/{provider_id}` — approve/reject
- `GET /api/v1/admin/reports` — flagged profiles
- `PATCH /api/v1/admin/reports/{report_id}` — dismiss/suspend
- `GET /api/v1/admin/users` — user list with filters
- `PATCH /api/v1/admin/users/{user_id}/toggle` — enable/disable account
- `GET /api/v1/admin/analytics` — stats + graphs

# Nirbhor — Provider Public Profile, Broadcast Status, Admin APIs + FCM Setup

## File Map

```
app/
├── schemas/
│   ├── provider_schema.py     ← add PublicProviderProfile response
│   ├── admin_schema.py        ← new: all admin response schemas
│   └── urgent_schema.py       ← add BroadcastStatusResponse
├── repositories/
│   ├── provider_repository.py ← add get_public_profile
│   ├── admin_repository.py    ← new
│   └── urgent_repository.py   ← add get_broadcast_status
├── services/
│   ├── provider_service.py    ← add get_public_profile
│   ├── admin_service.py       ← new
│   └── urgent_service.py      ← add get_broadcast_status
├── api/v1/
│   ├── providers.py           ← add GET /{provider_id}/public
│   ├── admin.py               ← new
│   └── urgent.py              ← add GET /{id}/status
└── services/
    └── notification_service.py ← FCM implementation
```

---

## i18n keys to add

```python
"provider_not_found":           {"en": "Provider not found.",                          "bn": "প্রোভাইডার পাওয়া যায়নি।"},
"report_not_found":             {"en": "Report not found.",                            "bn": "রিপোর্ট পাওয়া যায়নি।"},
"user_not_found":               {"en": "User not found.",                              "bn": "ব্যবহারকারী পাওয়া যায়নি।"},
"verification_updated":         {"en": "Verification status updated.",                 "bn": "যাচাইকরণ অবস্থা আপডেট হয়েছে।"},
"user_status_updated":          {"en": "User status updated.",                         "bn": "ব্যবহারকারীর অবস্থা আপডেট হয়েছে।"},
"report_status_updated":        {"en": "Report status updated.",                       "bn": "রিপোর্টের অবস্থা আপডেট হয়েছে।"},
"admin_only":                   {"en": "Admin access required.",                       "bn": "শুধুমাত্র অ্যাডমিন অ্যাক্সেস প্রয়োজন।"},
"rejection_reason_required":    {"en": "Rejection reason is required.",                "bn": "প্রত্যাখ্যানের কারণ প্রদান করুন।"},
```

---

## 1. Schemas

### `app/schemas/provider_schema.py` — add public profile response

```python
# Add to your existing provider_schema.py

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class PublicSkill(BaseModel):
    id: int
    name: str   # localized

    model_config = {"from_attributes": True}


class PublicProviderProfile(BaseModel):
    """
    Public-facing provider profile — visible to seekers.
    Phone is intentionally excluded (revealed only after booking initiation).
    NID urls excluded (private documents).
    """
    user_id: UUID
    name: str                           # localized
    photo_url: str | None
    verification_level: str
    average_rating: float | None
    working_radius_km: int
    has_smartphone: bool
    is_available: bool
    ai_review_summary: str | None       # localized
    skills: list[PublicSkill]
    last_active_at: datetime | None

    model_config = {"from_attributes": True}
```

### `app/schemas/urgent_schema.py` — add status response

```python
# Add to your existing urgent_schema.py

class BroadcastStatusResponse(BaseModel):
    """
    Seeker polls this to check if their urgent broadcast was claimed.
    Returns claimed provider's name only — phone is shared via FCM separately.
    In your current stub phase the seeker can poll this endpoint as fallback.
    """
    broadcast_id: UUID
    status: BroadcastStatus
    expires_at: datetime
    claimed_by_name: str | None     # None if not yet claimed
    claimed_at: datetime | None     # None if not yet claimed

    model_config = {"from_attributes": True}
```

### `app/schemas/admin_schema.py` — new

```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Literal


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

    model_config = {"from_attributes": True}


class VerificationActionSchema(BaseModel):
    """Admin approves or rejects a provider's verification request."""
    action: Literal["approve", "reject"]
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
    status: str
    booking_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportActionSchema(BaseModel):
    action: Literal["dismiss", "suspend", "reviewed"]


class ReportActionResponse(BaseModel):
    report_id: UUID
    status: str
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

    model_config = {"from_attributes": True}


class AdminUserDetail(AdminUserListItem):
    """Extended detail for single user view."""
    total_bookings: int
    average_rating: float | None    # providers only
    verification_level: str | None  # providers only
    verification_status: str | None # providers only


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
```

---

## 2. Repositories

### `app/repositories/provider_repository.py` — add public profile fetch

```python
# Add to your existing ProviderRepository

async def get_public_profile(
    self, provider_id: UUID, lang: str
) -> dict | None:
    """
    Fetch everything needed for a provider's public profile card.
    Returns None if provider does not exist or is not active.
    """
    from app.models.skill import Skill
    from app.models.provider_skill_link import ProviderSkillLink
    from sqlalchemy import func

    # Fetch user + profile in one join
    result = await self.db.execute(
        select(User, ProviderProfile)
        .join(ProviderProfile, User.id == ProviderProfile.user_id)
        .where(User.id == provider_id)
        .where(User.is_active == True)
    )
    row = result.first()
    if not row:
        return None

    user, profile = row

    # Fetch skills with localized names
    name_col = Skill.name_bn if lang == "bn" else Skill.name_en
    skills_result = await self.db.execute(
        select(Skill.id, name_col.label("name"))
        .join(ProviderSkillLink, Skill.id == ProviderSkillLink.skill_id)
        .where(ProviderSkillLink.provider_id == provider_id)
    )
    skills = [{"id": r.id, "name": r.name} for r in skills_result.all()]

    # Localized name and AI summary
    name = (
        (user.name_bn or user.name_en) if lang == "bn" else user.name_en
    )
    ai_summary = (
        (profile.ai_review_summary_bn or profile.ai_review_summary_en)
        if lang == "bn"
        else profile.ai_review_summary_en
    )

    return {
        "user_id": user.id,
        "name": name,
        "photo_url": profile.photo_url,
        "verification_level": profile.verification_level.value,
        "average_rating": profile.average_rating,
        "working_radius_km": profile.working_radius_km,
        "has_smartphone": profile.has_smartphone,
        "is_available": profile.is_available,
        "ai_review_summary": ai_summary,
        "skills": skills,
        "last_active_at": user.last_active_at,
    }
```

### `app/repositories/urgent_repository.py` — add status fetch

```python
# Add to your existing UrgentRepository

async def get_broadcast_status(
    self, broadcast_id: UUID
) -> dict | None:
    """Fetch broadcast + claimed provider name if claimed."""
    from app.models.user import User as UserModel

    ClaimedProvider = aliased(UserModel, name="claimed_provider")

    result = await self.db.execute(
        select(UrgentBroadcast, ClaimedProvider.name_en.label("claimed_name"))
        .outerjoin(
            ClaimedProvider,
            UrgentBroadcast.claimed_by_provider_id == ClaimedProvider.id,
        )
        .where(UrgentBroadcast.id == broadcast_id)
    )
    row = result.first()
    if not row:
        return None

    broadcast, claimed_name = row
    return {
        "broadcast_id": broadcast.id,
        "status": broadcast.status,
        "expires_at": broadcast.expires_at,
        "claimed_by_name": claimed_name,
        "claimed_at": None,  # add claimed_at column to model if needed
    }
```

### `app/repositories/admin_repository.py` — new

```python
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, update
from sqlalchemy.orm import aliased

from app.models.user import User, Role
from app.models.provider_profile import ProviderProfile, VerificationStatus, VerificationLevel
from app.models.booking import Booking, BookingStatus
from app.models.user_report import UserReport, ReportStatus


class AdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Dashboard ─────────────────────────────────────────────────────────────

    async def get_dashboard_counts(self) -> dict:
        now = datetime.now(timezone.utc)

        total_users = await self.db.scalar(select(func.count()).select_from(User))
        total_providers = await self.db.scalar(
            select(func.count()).select_from(User).where(User.role == Role.PROVIDER)
        )
        total_seekers = await self.db.scalar(
            select(func.count()).select_from(User).where(User.role == Role.SEEKER)
        )
        total_bookings = await self.db.scalar(
            select(func.count()).select_from(Booking)
        )
        pending_verifications = await self.db.scalar(
            select(func.count())
            .select_from(ProviderProfile)
            .where(ProviderProfile.verification_status == VerificationStatus.PENDING)
        )
        pending_reports = await self.db.scalar(
            select(func.count())
            .select_from(UserReport)
            .where(UserReport.status == ReportStatus.PENDING)
        )
        active_today = await self.db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.PROVIDER)
            .where(User.last_active_at >= now - timedelta(hours=24))
        )

        return {
            "total_users": total_users or 0,
            "total_providers": total_providers or 0,
            "total_seekers": total_seekers or 0,
            "total_bookings": total_bookings or 0,
            "pending_verifications": pending_verifications or 0,
            "pending_reports": pending_reports or 0,
            "active_providers_today": active_today or 0,
        }

    # ── Verifications ─────────────────────────────────────────────────────────

    async def get_pending_verifications(self) -> list:
        result = await self.db.execute(
            select(User, ProviderProfile)
            .join(ProviderProfile, User.id == ProviderProfile.user_id)
            .where(ProviderProfile.verification_status == VerificationStatus.PENDING)
            .order_by(ProviderProfile.updated_at.asc())   # oldest first
        )
        return result.all()

    async def get_provider_for_verification(
        self, provider_id: UUID
    ) -> tuple | None:
        result = await self.db.execute(
            select(User, ProviderProfile)
            .join(ProviderProfile, User.id == ProviderProfile.user_id)
            .where(User.id == provider_id)
        )
        return result.first()

    async def approve_verification(self, provider_id: UUID) -> ProviderProfile:
        profile = await self.db.get(ProviderProfile, provider_id)
        profile.verification_status = VerificationStatus.APPROVED
        profile.verification_level = VerificationLevel.VERIFIED
        profile.verification_rejection_reason = None
        await self.db.flush()
        return profile

    async def reject_verification(
        self, provider_id: UUID, reason: str
    ) -> ProviderProfile:
        profile = await self.db.get(ProviderProfile, provider_id)
        profile.verification_status = VerificationStatus.REJECTED
        profile.verification_rejection_reason = reason
        await self.db.flush()
        return profile

    # ── Reports ───────────────────────────────────────────────────────────────

    async def get_reports(self, status_filter: str | None = None) -> list:
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
        report_id: UUID,
        new_status: ReportStatus,
    ) -> UserReport:
        report = await self.db.get(UserReport, report_id)
        report.status = new_status
        await self.db.flush()
        return report

    async def suspend_user(self, user_id: UUID) -> User:
        user = await self.db.get(User, user_id)
        user.is_active = False
        await self.db.flush()
        return user

    # ── Users ─────────────────────────────────────────────────────────────────

    async def get_users(
        self,
        role_filter: str | None = None,
        is_active_filter: bool | None = None,
    ) -> list[User]:
        stmt = select(User).order_by(User.created_at.desc())
        if role_filter:
            stmt = stmt.where(User.role == role_filter)
        if is_active_filter is not None:
            stmt = stmt.where(User.is_active == is_active_filter)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_detail(self, user_id: UUID) -> dict | None:
        user = await self.db.get(User, user_id)
        if not user:
            return None

        total_bookings = await self.db.scalar(
            select(func.count())
            .select_from(Booking)
            .where(
                (Booking.seeker_id == user_id) | (Booking.provider_id == user_id)
            )
        )

        profile = None
        if user.role == Role.PROVIDER:
            profile = await self.db.get(ProviderProfile, user_id)

        return {
            "user": user,
            "total_bookings": total_bookings or 0,
            "profile": profile,
        }

    async def toggle_user_active(self, user_id: UUID) -> User:
        user = await self.db.get(User, user_id)
        user.is_active = not user.is_active
        await self.db.flush()
        return user

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_analytics(self) -> dict:
        now = datetime.now(timezone.utc)

        total_users = await self.db.scalar(select(func.count()).select_from(User))
        total_bookings = await self.db.scalar(select(func.count()).select_from(Booking))
        avg_rating = await self.db.scalar(
            select(func.avg(ProviderProfile.average_rating))
            .where(ProviderProfile.average_rating.is_not(None))
        )
        seeker_count = await self.db.scalar(
            select(func.count()).select_from(User).where(User.role == Role.SEEKER)
        )
        provider_count = await self.db.scalar(
            select(func.count()).select_from(User).where(User.role == Role.PROVIDER)
        )
        active_providers = await self.db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.PROVIDER)
            .where(User.last_active_at >= now - timedelta(days=30))
        )

        # Bookings per week for last 8 weeks
        # DATE_TRUNC groups timestamps into week buckets
        from sqlalchemy import text
        weekly_result = await self.db.execute(
            select(
                func.date_trunc("week", Booking.created_at).label("week_start"),
                func.count().label("count"),
            )
            .where(Booking.created_at >= now - timedelta(weeks=8))
            .group_by(text("week_start"))
            .order_by(text("week_start"))
        )
        bookings_per_week = [
            {"week_start": r.week_start, "count": r.count}
            for r in weekly_result.all()
        ]

        seeker_count = seeker_count or 0
        provider_count = provider_count or 0
        ratio = round(seeker_count / provider_count, 2) if provider_count > 0 else None

        return {
            "total_users": total_users or 0,
            "total_bookings": total_bookings or 0,
            "average_provider_rating": round(float(avg_rating), 2) if avg_rating else None,
            "active_providers_count": active_providers or 0,
            "seeker_count": seeker_count,
            "provider_count": provider_count,
            "seeker_to_provider_ratio": ratio,
            "bookings_per_week": bookings_per_week,
        }
```

---

## 3. Services

### `app/services/provider_service.py` — add public profile

```python
# Add to your existing ProviderService

@staticmethod
async def get_public_profile(
    provider_id: UUID,
    db: AsyncSession,
    lang: str,
) -> PublicProviderProfile:
    from app.repositories.provider_repository import ProviderRepository
    repo = ProviderRepository(db)
    data = await repo.get_public_profile(provider_id, lang)
    if not data:
        raise DomainValidationError(t("provider_not_found", lang))
    return PublicProviderProfile(**data)
```

### `app/services/urgent_service.py` — add broadcast status

```python
# Add to your existing UrgentService

@staticmethod
async def get_broadcast_status(
    broadcast_id: UUID,
    db: AsyncSession,
    lang: str,
) -> BroadcastStatusResponse:
    urgent_repo = UrgentRepository(db)
    data = await urgent_repo.get_broadcast_status(broadcast_id)
    if not data:
        raise DomainValidationError(t("broadcast_not_found", lang))
    return BroadcastStatusResponse(**data)
```

### `app/services/admin_service.py` — new

```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.repositories.admin_repository import AdminRepository
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
from app.models.user_report import ReportStatus
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
                nid_front_url=profile.nid_front_url,
                nid_back_url=profile.nid_back_url,
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
        repo = AdminRepository(db)

        row = await repo.get_provider_for_verification(provider_id)
        if not row:
            raise DomainValidationError(t("provider_not_found", lang))

        if data.action == "approve":
            profile = await repo.approve_verification(provider_id)
            logger.info(f"Admin approved verification for provider {provider_id}")
            # TODO: send FCM to provider — "Your account is now verified!"
        else:
            if not data.rejection_reason:
                raise DomainValidationError(t("rejection_reason_required", lang))
            profile = await repo.reject_verification(provider_id, data.rejection_reason)
            logger.info(
                f"Admin rejected verification for provider {provider_id}: "
                f"{data.rejection_reason}"
            )
            # TODO: send FCM to provider — "Your verification was rejected: {reason}"

        await db.commit()

        return VerificationActionResponse(
            user_id=provider_id,
            verification_status=profile.verification_status.value,
            verification_level=profile.verification_level.value,
            message=t("verification_updated", lang),
        )

    @staticmethod
    async def get_reports(
        db: AsyncSession,
        lang: str,
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
        repo = AdminRepository(db)

        report = await repo.get_report_by_id(report_id)
        if not report:
            raise DomainValidationError(t("report_not_found", lang))

        affected_user_id = None

        if data.action == "suspend":
            # Suspend the reported user and mark report as ACTION_TAKEN
            await repo.suspend_user(report.reported_user_id)
            await repo.update_report_status(report_id, ReportStatus.ACTION_TAKEN)
            affected_user_id = report.reported_user_id
            logger.info(
                f"Admin suspended user {report.reported_user_id} "
                f"via report {report_id}"
            )
        elif data.action == "dismiss":
            await repo.update_report_status(report_id, ReportStatus.REVIEWED)
            logger.info(f"Admin dismissed report {report_id}")
        elif data.action == "reviewed":
            await repo.update_report_status(report_id, ReportStatus.REVIEWED)

        await db.commit()

        return ReportActionResponse(
            report_id=report_id,
            status=data.action,
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
                name=u.name_en,
                phone=u.phone_en,
                role=u.role.value,
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

        u = data["user"]
        profile = data["profile"]

        return AdminUserDetail(
            user_id=u.id,
            name=u.name_en,
            phone=u.phone_en,
            role=u.role.value,
            is_active=u.is_active,
            last_active_at=u.last_active_at,
            created_at=u.created_at,
            total_bookings=data["total_bookings"],
            average_rating=profile.average_rating if profile else None,
            verification_level=profile.verification_level.value if profile else None,
            verification_status=profile.verification_status.value if profile else None,
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
        return {
            "user_id": user_id,
            "is_active": user.is_active,
            "message": t("user_status_updated", lang),
        }

    @staticmethod
    async def get_analytics(db: AsyncSession) -> AdminAnalyticsResponse:
        repo = AdminRepository(db)
        data = await repo.get_analytics()
        return AdminAnalyticsResponse(**data)
```

---

## 4. Routers

### `app/api/v1/providers.py` — add public profile endpoint

```python
# Add to your existing providers router

from app.schemas.provider_schema import PublicProviderProfile
from app.services.provider_service import ProviderService

@router.get("/{provider_id}/public", response_model=PublicProviderProfile)
async def get_provider_public_profile(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),   # any logged-in user
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Seeker taps a provider card to see their full public profile.
    Phone is NOT included — only revealed after booking initiation.
    """
    return await ProviderService.get_public_profile(
        provider_id=provider_id,
        db=db,
        lang=lang,
    )
```

### `app/api/v1/urgent.py` — add status endpoint

```python
# Add to your existing urgent router

from app.schemas.urgent_schema import BroadcastStatusResponse

@router.get("/broadcast/{broadcast_id}/status", response_model=BroadcastStatusResponse)
async def get_broadcast_status(
    broadcast_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Seeker polls this to check if their urgent broadcast was claimed.
    Frontend polls every 10-15 seconds while the countdown timer is showing.
    When status changes to CLAIMED, show the provider name on screen.
    Stop polling when status is CLAIMED or EXPIRED.
    """
    return await UrgentService.get_broadcast_status(
        broadcast_id=broadcast_id,
        db=db,
        lang=lang,
    )
```

### `app/api/v1/admin.py` — new

```python
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.core.security import get_current_user
from app.models.user import User, Role
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
from app.services.admin_service import AdminService
from app.core.exceptions import DomainValidationError
from app.core.i18n import t

router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: blocks non-admin users from all admin routes."""
    if current_user.role != Role.ADMIN:
        raise DomainValidationError("Admin access required.")
    return current_user


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=AdminDashboardResponse)
async def admin_dashboard(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    return await AdminService.get_dashboard(db=db)


# ── Verifications ──────────────────────────────────────────────────────────────

@router.get("/verifications", response_model=list[VerificationListItem])
async def list_pending_verifications(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """List all providers with PENDING verification status, oldest first."""
    return await AdminService.get_pending_verifications(db=db, lang=lang)


@router.patch(
    "/verifications/{provider_id}",
    response_model=VerificationActionResponse,
)
async def handle_verification(
    provider_id: UUID,
    data: VerificationActionSchema,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Approve or reject a provider's verification request.
    - approve → verification_level becomes VERIFIED, rejection_reason cleared
    - reject  → rejection_reason required, provider stays BASIC
    """
    return await AdminService.handle_verification(
        provider_id=provider_id,
        data=data,
        db=db,
        lang=lang,
    )


# ── Reports ────────────────────────────────────────────────────────────────────

@router.get("/reports", response_model=list[ReportListItem])
async def list_reports(
    status: str | None = Query(None, description="Filter: PENDING, REVIEWED, ACTION_TAKEN"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await AdminService.get_reports(db=db, lang=lang, status_filter=status)


@router.patch("/reports/{report_id}", response_model=ReportActionResponse)
async def handle_report(
    report_id: UUID,
    data: ReportActionSchema,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    - dismiss  → marks report REVIEWED, no action on reported user
    - reviewed → marks report REVIEWED
    - suspend  → marks report ACTION_TAKEN + sets reported user is_active=False
    """
    return await AdminService.handle_report(
        report_id=report_id,
        data=data,
        db=db,
        lang=lang,
    )


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[AdminUserListItem])
async def list_users(
    role: str | None = Query(None, description="Filter: SEEKER, PROVIDER, ADMIN"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    return await AdminService.get_users(
        db=db, role_filter=role, is_active_filter=is_active
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await AdminService.get_user_detail(
        user_id=user_id, db=db, lang=lang
    )


@router.patch("/users/{user_id}/toggle", status_code=200)
async def toggle_user_active(
    user_id: UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Enable or disable a user account. Toggles current is_active value."""
    return await AdminService.toggle_user_active(
        user_id=user_id, db=db, lang=lang
    )


# ── Analytics ──────────────────────────────────────────────────────────────────

@router.get("/analytics", response_model=AdminAnalyticsResponse)
async def get_analytics(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Stats for admin dashboard — totals, ratios, weekly booking graph data."""
    return await AdminService.get_analytics(db=db)
```

### Register in `app/api/v1/router.py`

```python
from app.api.v1 import admin

api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
```

---

## 5. FCM Setup — Firebase Admin SDK

### Why Admin SDK (not the REST API directly)?

Firebase Admin SDK handles token management, retry logic, and batch sending
automatically. The REST API requires you to manage OAuth tokens yourself.
Admin SDK is the correct approach.

### Step 1: Get your `serviceAccountKey.json`

1. Go to https://console.firebase.google.com
2. Create a new project (name it "nirbhor" or similar)
3. Go to **Project Settings** (gear icon) → **Service Accounts** tab
4. Click **"Generate new private key"** → confirms → downloads a JSON file
5. Rename it to `serviceAccountKey.json`
6. **Never commit this file to git.** Add to `.gitignore` immediately:
   ```
   serviceAccountKey.json
   ```

### Step 2: Store the key securely

For local development: place the file at the project root and reference it
via an env variable. For Render.com production: paste the JSON content as an
environment variable (not a file).

```python
# app/core/config.py — add these settings
FIREBASE_CREDENTIALS_PATH: str = "serviceAccountKey.json"
# OR for production (JSON string in env var):
FIREBASE_CREDENTIALS_JSON: str | None = None
```

### Step 3: Install the SDK

```bash
pip install firebase-admin
```

Add to `requirements.txt`:
```
firebase-admin==6.5.0
```

### Step 4: Initialize Firebase once at startup

```python
# app/core/firebase.py

import json
import firebase_admin
from firebase_admin import credentials, messaging
from loguru import logger

from app.core.config import settings


def init_firebase() -> None:
    """
    Initialize Firebase Admin SDK once at app startup.
    Supports both file path (local dev) and JSON string (Render production).
    """
    if firebase_admin._apps:
        return  # already initialized

    try:
        if settings.FIREBASE_CREDENTIALS_JSON:
            # Production: JSON string stored in environment variable
            cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
        else:
            # Local development: JSON file on disk
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)

        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        raise


# Call in main.py lifespan:
# from app.core.firebase import init_firebase
# init_firebase()
```

### Step 5: The NotificationService

```python
# app/services/notification_service.py

from uuid import UUID
from firebase_admin import messaging
from loguru import logger


class NotificationService:

    @staticmethod
    async def send_urgent_broadcast(
        tokens: list[str],
        broadcast_id: UUID,
        skill_name: str,
    ) -> None:
        """
        Send high-priority FCM to all nearby providers simultaneously.
        Uses MulticastMessage for batch delivery (up to 500 tokens per call).
        """
        if not tokens:
            return

        message = messaging.MulticastMessage(
            tokens=tokens,
            data={
                # 'data' payload (not 'notification') so Flutter/React can handle
                # it even when app is backgrounded, and extract broadcast_id
                "type": "URGENT_BROADCAST",
                "broadcast_id": str(broadcast_id),
                "skill_name": skill_name,
            },
            notification=messaging.Notification(
                title=f"জরুরি কাজ! / Urgent Job!",
                body=f"আপনার কাছে কেউ {skill_name} চাইছেন। / Someone needs {skill_name} urgently.",
            ),
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"}
            ),
        )

        try:
            response = messaging.send_each_for_multicast(message)
            logger.info(
                f"Urgent broadcast FCM: {response.success_count} sent, "
                f"{response.failure_count} failed out of {len(tokens)} tokens"
            )
        except Exception as e:
            # FCM failure must never crash the booking flow
            logger.error(f"FCM urgent broadcast failed: {e}")

    @staticmethod
    async def send_booking_followup(
        seeker_fcm_token: str,
        booking_id: UUID,
        provider_name: str,
        attempt: int,
    ) -> None:
        """2-hour and 24-hour follow-up: 'Did you hire [provider]?'"""
        if not seeker_fcm_token:
            return

        message = messaging.Message(
            token=seeker_fcm_token,
            data={
                "type": "BOOKING_FOLLOWUP",
                "booking_id": str(booking_id),
                "attempt": str(attempt),
            },
            notification=messaging.Notification(
                title="বুকিং আপডেট / Booking Update",
                body=f"আপনি কি {provider_name} কে নিয়োগ করেছেন? / Did you hire {provider_name}?",
            ),
        )

        try:
            messaging.send(message)
            logger.info(
                f"Booking followup FCM sent: booking={booking_id} attempt={attempt}"
            )
        except Exception as e:
            logger.error(f"FCM booking followup failed: {e}")

    @staticmethod
    async def send_completion_prompt(
        seeker_fcm_token: str,
        booking_id: UUID,
        provider_name: str,
    ) -> None:
        """'Your job with [provider] should be done. Tap to review!'"""
        if not seeker_fcm_token:
            return

        message = messaging.Message(
            token=seeker_fcm_token,
            data={
                "type": "COMPLETION_PROMPT",
                "booking_id": str(booking_id),
            },
            notification=messaging.Notification(
                title="কাজ সম্পন্ন? / Job Done?",
                body=f"{provider_name} এর সাথে আপনার কাজ শেষ হয়ে থাকলে রিভিউ দিন।",
            ),
        )

        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM completion prompt failed: {e}")

    @staticmethod
    async def send_broadcast_expired(seeker_fcm_token: str) -> None:
        """'No one responded. Please try a manual search.'"""
        if not seeker_fcm_token:
            return

        message = messaging.Message(
            token=seeker_fcm_token,
            data={"type": "BROADCAST_EXPIRED"},
            notification=messaging.Notification(
                title="কোনো সাড়া নেই / No Response",
                body="কেউ সাড়া দেননি। ম্যানুয়াল অনুসন্ধান করুন। / No one responded. Try manual search.",
            ),
        )

        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM broadcast expired notification failed: {e}")

    @staticmethod
    async def send_broadcast_claimed(
        seeker_fcm_token: str,
        provider_name: str,
    ) -> None:
        """Notify seeker that a provider accepted their urgent request."""
        if not seeker_fcm_token:
            return

        message = messaging.Message(
            token=seeker_fcm_token,
            data={"type": "BROADCAST_CLAIMED", "provider_name": provider_name},
            notification=messaging.Notification(
                title="প্রোভাইডার পাওয়া গেছে! / Provider Found!",
                body=f"{provider_name} আপনার অনুরোধ গ্রহণ করেছেন। / {provider_name} accepted your request.",
            ),
        )

        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM broadcast claimed notification failed: {e}")

    @staticmethod
    async def send_verification_approved(provider_fcm_token: str) -> None:
        message = messaging.Message(
            token=provider_fcm_token,
            data={"type": "VERIFICATION_APPROVED"},
            notification=messaging.Notification(
                title="যাচাইকরণ সম্পন্ন! / Verified!",
                body="আপনার অ্যাকাউন্ট যাচাই হয়েছে। এখন আপনি ব্লু টিক পাবেন।",
            ),
        )
        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM verification approved failed: {e}")
```

### Step 6: Wire FCM into main.py lifespan

```python
# app/main.py — in lifespan, before yield

from app.core.firebase import init_firebase
init_firebase()
```

### Step 7: Getting FCM tokens from Flutter/React

Flutter (provider/seeker mobile app):
```dart
// In Flutter — add firebase_messaging package
// pubspec.yaml: firebase_messaging: ^14.x.x

final fcmToken = await FirebaseMessaging.instance.getToken();
// Send this token to your backend after login:
// POST /api/v1/fcm/token  { "token": fcmToken, "device_type": "ANDROID" }
```

You already have an `fcm_tokens` table. You need one small endpoint to
receive and store tokens:

```python
# Add to app/api/v1/auth.py or a new fcm.py router

@router.post("/fcm/token", status_code=201)
async def register_fcm_token(
    token: str,
    device_type: str,   # ANDROID, IOS, WEB
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Called by Flutter/React after login to register the device FCM token."""
    from app.models.fcm_token import FCMToken
    from sqlalchemy.dialects.postgresql import insert

    # Upsert — avoid duplicates if same token registered twice
    stmt = insert(FCMToken).values(
        user_id=current_user.id,
        token=token,
        device_type=device_type,
    ).on_conflict_do_nothing()

    await db.execute(stmt)
    await db.commit()
    return {"registered": True}
```

---

## What's Left After This

**Done after this batch:**
- All seeker flows ✓
- All provider flows ✓
- All admin flows ✓
- FCM infrastructure ✓

**Remaining before submission:**

1. **Wire FCM into job stubs** — replace `# TODO` comments in
   `booking_jobs.py` and `urgent_jobs.py` with actual
   `NotificationService` calls. You need to fetch the user's FCM token
   from `fcm_tokens` table before calling each notification method.

2. **Alembic migration** — run `alembic revision --autogenerate` to pick up
   any model changes, then `alembic upgrade head`.

3. **Test the admin endpoints** — create an admin user directly in the DB
   (seed script) since there's no admin registration endpoint by design.

4. **Render + NeonDB deployment** — set `FIREBASE_CREDENTIALS_JSON` as an
   env var on Render (paste the full JSON content, not the file path).
   Set `SCHEDULER_ENABLED=true` on only one Render worker instance to
   prevent duplicate job runs.

5. **AI review summarization** — the weekly cron job that batches reviews
   and calls an AI model to generate `ai_review_summary_en/bn` on
   `provider_profiles`. This is a nice-to-have for the capstone demo.
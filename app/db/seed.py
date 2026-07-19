from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.category_model import Category
from app.models.provider_profile_model import ProviderProfile
from app.models.provider_skill_link_model import ProviderSkillLink
from app.models.skill_model import Skill
from loguru import logger
from app.core.security import Security
from app.models.user_model import Role, User
from datetime import datetime, timedelta, timezone


async def seed_categories_and_skills(db: AsyncSession) -> None:
    """Insert initial categories and skills if they don't exist."""

    # check if already seeded
    existing = await db.scalar(select(Category).limit(1))
    if existing:
        logger.info("Categories and skills already seeded. Skipping...")
        return  # already seeded, skip

    categories_data = [
        {
            "name_en": "Manual Labor",
            "name_bn": "কায়িক শ্রম",
            "skills": [
                {"name_en": "Day Laborer / Heavy Lifting",
                    "name_bn": "দিনমজুর / ভারি কাজ"},
                {"name_en": "Furniture Shifting Helper",
                    "name_bn": "আসবাবপত্র স্থানান্তর"},
                {"name_en": "Warehouse Helper", "name_bn": "গুদামঘরের সহকারী"},
            ]
        },
        {
            "name_en": "Home Repairs",
            "name_bn": "বাসা মেরামত",
            "skills": [
                {"name_en": "Electrician", "name_bn": "ইলেকট্রিশিয়ান"},
                {"name_en": "Plumber", "name_bn": "প্লাম্বার"},
                {"name_en": "AC Servicing Helper", "name_bn": "এসি সার্ভিসিং"},
                {"name_en": "Appliance Repair",
                    "name_bn": "হোম অ্যাপ্লায়েন্স মেরামত"},
            ]
        },
        {
            "name_en": "Cleaning & Domestic",
            "name_bn": "পরিষ্কার ও গৃহস্থালি",
            "skills": [
                {"name_en": "Home Maid", "name_bn": "ছুটা বুয়া"},
                {"name_en": "Deep Cleaning Helper", "name_bn": "ডিপ ক্লিনিং"},
                {"name_en": "Painting Helper", "name_bn": "রংমিস্ত্রি সহকারী"},
            ]
        },
        {
            "name_en": "Transportation",
            "name_bn": "পরিবহন",
            "skills": [
                {"name_en": "Van Driver / 3-Wheeler", "name_bn": "ভ্যান চালক"},
                {"name_en": "Small Pickup Driver", "name_bn": "পিকআপ চালক"},
            ]
        },
    ]

    for cat_data in categories_data:
        category = Category(
            name_en=cat_data["name_en"],
            name_bn=cat_data["name_bn"],
        )
        db.add(category)
        await db.flush()  # get category.id without committing

        for skill_data in cat_data["skills"]:
            skill = Skill(
                name_en=skill_data["name_en"],
                name_bn=skill_data["name_bn"],
                category_id=category.id,
            )
            db.add(skill)

    await db.commit()
    logger.success("✅ Seed data inserted successfully")


async def create_admin_user(db: AsyncSession) -> None:
    existing = await db.execute(select(User).where(User.phone_en == "01700000000"))
    if existing.scalar_one_or_none():
        logger.info("Admin already seeded. Skipping...")
        return
    admin = User(
        phone_en="01700000000",
        password_hash=Security.hash_password("admin123"),
        role=Role.ADMIN,
        name_en="Admin",
        name_bn="অ্যাডমিন",
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    logger.success("✅ Admin user created successfully")


async def seed_load_test_seeker(db: AsyncSession) -> None:
    """Creates test accounts for load testing. Run before locust."""
    from app.core.security import Security

    # check if already seeded
    existing = await db.execute(select(User).where(User.phone_en == "01700000001"))
    if existing.scalar_one_or_none():
        logger.info("Load test seeker already seeded. Skipping...")
        return

    password_hash = Security.hash_password("password123")
    seekers_to_add = []

    for i in range(1, 11):
        # Generates: "01700000001", "01700000002", ..., "01700000010"
        phone = f"017000000{i:02d}"

        seeker = User(
            phone_en=phone,
            password_hash=password_hash,
            role=Role.SEEKER,
            name_en=f"Load Test Seeker {i}",
            name_bn=f"লোড টেস্ট সিকার {i}",
            is_active=True,
            preferred_lang="en",
            last_active_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        seekers_to_add.append(seeker)

    db.add_all(seekers_to_add)

    await db.commit()
    logger.success("✅ 10 Load test Seeker created successfully")


async def seed_load_test_provider(db: AsyncSession) -> None:
    """Creates test accounts for load testing. Run before locust."""
    from app.core.security import Security
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    # check if already seeded
    existing = await db.execute(select(User).where(User.phone_en == "01800000001"))
    if existing.scalar_one_or_none():
        logger.info("Load test provider already seeded. Skipping...")
        return

    first_skill = await db.scalar(select(Skill).limit(1))
    password_hash = Security.hash_password("password123")
    now = datetime.now(timezone.utc)

    for i in range(1, 11):
        phone = f"018000000{i:02d}"

        provider = User(
            phone_en=phone,
            password_hash=password_hash,
            role=Role.PROVIDER,
            name_en=f"Load Test Provider {i}",
            name_bn=f"লোড টেস্ট প্রোভাইডার {i}",
            is_active=True,
            preferred_lang="bn",
            last_active_at=now,
            created_at=now,
        )
        db.add(provider)
        await db.flush()  # Generates provider.id

        # Profile setup (Slightly shifts coordinates so they aren't stacked on top of each other)
        profile = ProviderProfile(
            user_id=provider.id,
            base_location=from_shape(
                Point(90.3950 + (i * 0.001), 23.7540 + (i * 0.001)), srid=4326),
            location_updated_at=now - timedelta(days=20),
            working_radius_km=5,
            radius_updated_at=now - timedelta(days=20),
            has_smartphone=True,
            is_available=True,
            warning_status=False,
        )
        db.add(profile)

        # Skill Link setup
        if first_skill:
            link = ProviderSkillLink(
                provider_id=provider.id,
                skill_id=first_skill.id,
            )
            db.add(link)

    await db.commit()
    logger.success(
        "✅ 10 Load test Providers + profiles + skill links created successfully"
    )

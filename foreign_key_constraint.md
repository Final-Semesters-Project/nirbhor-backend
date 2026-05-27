

<!-- SEED DATA FOR CATEGORY AND SKILLS -->
```python
# app/db/seed.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.category_model import Category
from app.models.skill_model import Skill


async def seed_categories_and_skills(db: AsyncSession) -> None:
    """Insert initial categories and skills if they don't exist."""

    # check if already seeded
    existing = await db.scalar(select(Category).limit(1))
    if existing:
        return  # already seeded, skip

    categories_data = [
        {
            "name_en": "Manual Labor",
            "name_bn": "কায়িক শ্রম",
            "skills": [
                {"name_en": "Day Laborer / Heavy Lifting", "name_bn": "দিনমজুর / ভারি কাজ"},
                {"name_en": "Furniture Shifting Helper", "name_bn": "আসবাবপত্র স্থানান্তর"},
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
                {"name_en": "Appliance Repair", "name_bn": "হোম অ্যাপ্লায়েন্স মেরামত"},
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
    print("✅ Seed data inserted successfully")
```

# run it via lifespan
```python
# app/main.py
from contextlib import asynccontextmanager
from app.db.seed import seed_categories_and_skills
from app.db.session import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs once on startup
    setup_logging()
    async with AsyncSessionLocal() as db:
        await seed_categories_and_skills(db)
    yield


app = FastAPI(lifespan=lifespan, ...)
```
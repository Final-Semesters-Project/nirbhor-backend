1. Error for provider_skill_links table:
not passing a valid skill_id:
 ```Provider registration failed: (sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) <class 'asyncpg.exceptions.ForeignKeyViolationError'>: insert or update on table "provider_skill_links" violates foreign key constraint "provider_skill_links_skill_id_fkey"```

2. Error for skill table:
category id f_key doesn't exists
Seeker registration failed: (sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) <class 'asyncpg.exceptions.ForeignKeyViolationError'>: insert or update on table "skills" violates foreign key constraint "skills_category_id_fkey"


# Integrity error parser

```python
import re


def parse_integrity_error(error_msg: str) -> str:

Parse/Extract readable message from PostgreSQL IntegrityError
example: 'Key (registration)=(213313316) already exists'
output: 'Registration 213313316 already exists'

    # constraint name checks

    # --- Student Tables Constraints ---
    if "students_registration_key" in error_msg:
        # get the value using Regex
        match = re.search(r"Key \(registration\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"Registration number '{val}' already exists in our records."

    if "students_user_id_key" in error_msg:
        return "This user is already assigned to another student profile."

    # --- User Tables Constraints ---
    if "users_username_key" in error_msg:
        match = re.search(r"Key \(username\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"The username '{val}' is already registered."

    if "users_email_key" in error_msg:
        match = re.search(r"Key \(email\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"The email address '{val}' is already registered."

    if "users_mobile_number_key" in error_msg or "mobile_number" in error_msg.lower():
        return "This mobile number is already used for another user."

    # --- Teacher Tables Constraints ---
    if "teachers_user_id_key" in error_msg:
        return "This user is already assigned to another teacher profile."

    # --- Department Tables Constraints ---
    if "departments_department_name_key" in error_msg:
        match = re.search(r"Key \(department_name\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"A department named '{val}' already exists."

    # --- Semester Tables Constraints ---
    if "semesters_semester_name_key" in error_msg:
        match = re.search(r"Key \(semester_name\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"Semester name '{val}' already exists."

    if "semesters_semester_number_key" in error_msg:
        match = re.search(r"Key \(semester_number\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"Semester number '{val}' is already assigned."

    # --- Subject Tables Constraints ---
    if "subjects_subject_code_key" in error_msg:
        match = re.search(r"Key \(subject_code\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"A subject with code '{val}' already exists."

    # --- Mark Tables Constraints ---
    if "unique_mark_record" in error_msg:
        return "A mark entry already exists for this student in the selected subject and semester."

    # If no constraint name found (default message)
    return "A data integrity error has occurred. Please check your input and try again."
```

# exceptions.py
```python

class DomainIntegrityError(Exception):
    def __init__(self, error_message: str, raw_error: str | None = None):
        self.error_message = error_message
        self.raw_error = raw_error
        super().__init__(error_message)

    def __str__(self) -> str:
        return self.error_message
```


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
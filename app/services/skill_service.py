from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.skill_model import Skill
from app.repositories.skill_repository import SkillRepository
from app.schemas.skill_schema import SkillCreateSchema
from fastapi import HTTPException, status


class SkillService:

    @staticmethod
    async def create_skill(
        data: SkillCreateSchema,
        db: AsyncSession,
    ) -> dict:
        # create an instance of SkillRepository
        skill_repo = SkillRepository(db)

        # check if skill already exists
        existing = await skill_repo.get_by_name(
            name_en=data.name_en,
            name_bn=data.name_bn
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Skill already exists",
            )

        # TODO: check if category exists
        # category = await db.get(Category, data.category_id)
        # if not category:
        #     raise HTTPException(
        #         status_code=400,
        #         detail="The selected category does not exist." if lang == "en" else "নির্বাচিত ক্যাটাগরিটির কোনো অস্তিত্ব নেই।"
        #     )

        try:
            skill = await skill_repo.create(
                name_en=data.name_en,
                name_bn=data.name_bn,
                category_id=data.category_id
            )
            await db.commit()
            logger.success(f"Skill: {skill.name_en} created successfully")

            return {
                "message": "Skill created successfully",
            }
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Seeker registration failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed. Please try again.",
            )

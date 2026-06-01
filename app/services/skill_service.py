from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainIntegrityError
from app.core.i18n import t
from app.core.integrity_error_parser import parse_integrity_error
from app.models.category_model import Category
from app.models.skill_model import Skill
from app.repositories.skill_repository import SkillRepository
from app.schemas.skill_schema import SkillCreateSchema
from fastapi import HTTPException, status


class SkillService:

    @staticmethod
    async def create_skill(
        data: SkillCreateSchema,
        db: AsyncSession,
        lang: str
    ) -> dict:
        # create an instance of SkillRepository
        skill_repo = SkillRepository(db)

        # check if skill already exists
        existing = await skill_repo.get_by_name(
            name_en=data.name_en,
            name_bn=data.name_bn
        )

        if existing:
            logger.error(f"Skill {data.name_en} already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t("existing_skill", lang),
            )

        category = await db.get(Category, data.category_id)
        if not category:
            logger.error(f"Category {data.category_id} does not exist")
            raise HTTPException(
                status_code=400,
                detail=t("category_does_not_exists", lang),
            )

        try:
            skill = await skill_repo.create(
                name_en=data.name_en,
                name_bn=data.name_bn,
                category_id=data.category_id
            )
            await db.commit()
            logger.success(f"Skill: {skill.name_en} created successfully")

            return {
                "message": t("skill_created", lang),
            }
        except IntegrityError as e:
            await db.rollback()
            raw = str(e.orig) if e.orig else str(e)
            readable = parse_integrity_error(raw, lang)
            logger.error(f"IntegrityError in skill creation: {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.critical(f"Unexpected error in provider registration: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=t("skill_creation_failed", lang),
            )

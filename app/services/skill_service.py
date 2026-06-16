from asyncpg import ForeignKeyViolationError, UniqueViolationError
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t
from app.core.integrity_error_parser import parse_integrity_error
from app.models.category_model import Category
from app.models.skill_model import Skill
from app.repositories.skill_repository import SkillRepository
from app.schemas.skill_schema import SkillCreateSchema, SkillResponseSchema
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
            raise DomainIntegrityError(
                error_message=t("existing_skill", lang),
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

            # e.orig may be a string (SQLAlchemy asyncpg dialect behaviour) or
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
                logger.warning(f"FK violation in skill creation: {raw}")
                raise DomainValidationError(
                    error_message=readable,
                    raw_error=raw
                )
            if is_unique:
                logger.warning(
                    f"Unique violation in skill creation: {raw}")
                raise DomainIntegrityError(
                    error_message=readable,
                    raw_error=raw
                )

            logger.error(f"Unhandled IntegrityError in skill creation: {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except (DomainIntegrityError, DomainValidationError):
            # let domain exceptions bubble up untouched to the global handler
            raise
        except Exception as e:
            await db.rollback()
            logger.critical(f"Unexpected error in provider registration: {e}")
            raise

    @staticmethod
    async def get_skills_by_category(
        category_id: int, db: AsyncSession, lang: str
    ) -> list[SkillResponseSchema]:
        repo = SkillRepository(db)
        skills = await repo.get_skills_by_category(category_id)
        return [
            SkillResponseSchema(
                id=s.id,
                name=s.name_bn if lang == "bn" else s.name_en,
                category_id=s.category_id,
            )
            for s in skills
        ]

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainIntegrityError
from app.core.i18n import t
from app.core.integrity_error_parser import parse_integrity_error
from app.repositories.category_repository import CategoryRepository
from app.schemas.category_schema import CategoryCreateSchema


class CategoryService:

    @staticmethod
    async def create_category(
        data: CategoryCreateSchema,
        db: AsyncSession,
        lang: str
    ) -> dict:
        # create an instance of CategoryRepository
        category_repo = CategoryRepository(db)

        # check if category already exists
        existing = await category_repo.get_by_name(
            name_en=data.name_en,
            name_bn=data.name_bn
        )

        if existing:
            logger.error(f"Category {data.name_en} already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t("category_exists", lang),
            )

        try:
            await category_repo.create(
                name_en=data.name_en,
                name_bn=data.name_bn
            )
            await db.commit()

            # message = t("category_created", lang)
            return {
                "message": t("category_created", lang),
            }

        except IntegrityError as e:
            await db.rollback()
            raw = str(e.orig) if e.orig else str(e)
            readable = parse_integrity_error(raw, lang)
            logger.error(f"IntegrityError in category creation: {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.critical(f"Unexpected error in provider registration: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=t("category_creation_failed", lang),
            )

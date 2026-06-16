from asyncpg import ForeignKeyViolationError, UniqueViolationError
from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t
from app.core.integrity_error_parser import parse_integrity_error
from app.repositories.category_repository import CategoryRepository
from app.schemas.category_schema import CategoryCreateSchema, CategoryResponse


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
            raise DomainIntegrityError(
                error_message=t("category_exists", lang),
            )

        try:
            await category_repo.create(
                name_en=data.name_en,
                name_bn=data.name_bn
            )
            await db.commit()
            return {
                "message": t("category_created", lang),
            }

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
                logger.warning(f"FK violation in category creation: {raw}")
                raise DomainValidationError(
                    error_message=readable,
                    raw_error=raw
                )
            if is_unique:
                logger.warning(
                    f"Unique violation in category creation: {raw}")
                raise DomainIntegrityError(
                    error_message=readable,
                    raw_error=raw
                )

            logger.error(f"IntegrityError in category creation: {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except (DomainIntegrityError, DomainValidationError):
            # let domain exceptions bubble up untouched to the global handler
            raise
        except Exception as e:
            await db.rollback()
            logger.critical(f"Unexpected error in provider registration: {e}")
            raise

    @staticmethod
    async def get_all_categories(
        db: AsyncSession, lang: str
    ) -> list[CategoryResponse]:
        repo = CategoryRepository(db)
        categories = await repo.get_all_categories()
        return [
            CategoryResponse(
                id=c.id,
                name=c.name_bn if lang == "bn" else c.name_en,
            )
            for c in categories
        ]

from fastapi import Depends, HTTPException, status, APIRouter
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.i18n import MESSAGES, get_lang
from app.db.session import get_db_session
from app.schemas.category_schema import CategoryCreateSchema
from app.services.category_service import CategoryService


router = APIRouter(prefix="/category", tags=["Category Management"])


@router.post(
    "/create",
    response_model=dict,
    summary="Create a new category",
)
async def create_new_category(
    data: CategoryCreateSchema,
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await CategoryService.create_category(data=data, db=db, lang=lang)

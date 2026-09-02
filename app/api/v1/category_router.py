from fastapi import Depends, HTTPException, status, APIRouter
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user, get_current_admin
from app.core.i18n import MESSAGES, get_lang
from app.db.session import get_db_session
from app.models.user_model import User
from app.schemas.category_schema import CategoryCreateSchema, CategoryResponse
from app.services.category_service import CategoryService


router = APIRouter(prefix="/category", tags=["Category Management"])


@router.post(
    "/create",
    response_model=dict,
    summary="Create a new category",
)
async def create_new_category(
    data: CategoryCreateSchema,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await CategoryService.create_category(data=data, db=db, lang=lang)


@router.get("/list", response_model=list[CategoryResponse])
async def get_categories(
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """All categories for the seeker home page dropdown."""
    return await CategoryService.get_all_categories(db=db, lang=lang)

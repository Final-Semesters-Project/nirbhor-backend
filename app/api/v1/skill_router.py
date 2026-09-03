from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_admin, get_current_user
from app.core.i18n import MESSAGES, get_lang
from app.db.session import get_db_session
from app.models.user_model import User
from app.schemas.skill_schema import (
    SkillCreateSchema,
    SkillResponseSchema
)
from app.services.skill_service import SkillService

router = APIRouter(prefix="/skill", tags=["Skill Management"])


@router.post(
    "/create",
    response_model=dict,
    summary="Create a new skill",
)
async def create_new_skill(
    data: SkillCreateSchema,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await SkillService.create_skill(data=data, db=db, lang=lang)


@router.get("/{category_id}/skills", response_model=list[SkillResponseSchema])
async def get_skills_by_category(
    category_id: int,
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Skills under a category — populated after seeker selects a category."""
    return await SkillService.get_skills_by_category(
        category_id=category_id, db=db, lang=lang
    )

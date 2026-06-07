from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.i18n import MESSAGES, get_lang
from app.db.session import get_db_session
from app.schemas.skill_schema import (
    SkillCreateSchema
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
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await SkillService.create_skill(data=data, db=db, lang=lang)

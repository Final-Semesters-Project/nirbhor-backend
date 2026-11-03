from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.i18n import get_lang
from app.db.session import get_db_session
from app.models.user_model import User
from app.schemas.pagination_schema import PageResponse
from app.schemas.user_report_schema import (
    CreateUserReportSchema,
    UserReportListItem,
    UserReportResponse,
)
from app.services.user_report_service import UserReportService

router = APIRouter(prefix="/user-reports", tags=["Reports"])


@router.post("", response_model=UserReportResponse, status_code=201)
async def create_user_report(
    data: CreateUserReportSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await UserReportService.create_report(
        data=data,
        reporter_id=current_user.id,
        db=db,
        lang=lang,
    )


@router.get("/", response_model=PageResponse[UserReportListItem])
async def get_current_user_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await UserReportService.get_current_user_reports(
        reporter_id=current_user.id,
        db=db,
        lang=lang,
        page=page,
        page_size=page_size,
    )

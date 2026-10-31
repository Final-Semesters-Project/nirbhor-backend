from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_seeker
from app.db.session import get_db_session
from app.models.user_model import User
from app.schemas.seeker_schema import SeekerAddressUpdateSchema, SeekerAddressResponse
from app.services.seeker_service import SeekerService

# import get_current_seeker from the same place your other routers do

router = APIRouter(prefix="/seeker", tags=["Seeker Management"])


@router.get("/me/address", response_model=SeekerAddressResponse)
async def get_my_address(
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
):
    return await SeekerService.get_address(user_id=current_user.id, db=db)


@router.patch("/me/address")
async def update_my_address(
    data: SeekerAddressUpdateSchema,
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
):
    return await SeekerService.update_address(user_id=current_user.id, data=data, db=db)

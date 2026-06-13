from fastapi import APIRouter
from app.api.v1 import auth_router, skill_router, category_router, user_router, provider_router, bookings_router, search_router, urgent_router

api_router = APIRouter()


api_router.include_router(auth_router.router)
api_router.include_router(skill_router.router)
api_router.include_router(category_router.router)
api_router.include_router(user_router.router)
api_router.include_router(provider_router.router)
api_router.include_router(bookings_router.router)
api_router.include_router(search_router.router)
api_router.include_router(urgent_router.router)

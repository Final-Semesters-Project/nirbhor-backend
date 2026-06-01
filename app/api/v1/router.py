from fastapi import APIRouter
from app.api.v1 import auth_router, skill_router, category_router

api_router = APIRouter()


api_router.include_router(auth_router.router)
api_router.include_router(skill_router.router)
api_router.include_router(category_router.router)

from fastapi.responses import JSONResponse
from app.api.v1.auth_router import router as auth_router
from app.api.v1.skill_router import router as skill_router
from app.api.v1.category_router import router as category_router
from fastapi import FastAPI, Request, status
from app.core.config import settings
from app.core.exceptions import DomainIntegrityError, register_exception_handlers
from contextlib import asynccontextmanager
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs on startup, before any requests
    setup_logging()
    yield
    # runs on shutdown, after all requests


# check if in production or development
ENV = settings.APP_ENV or "development"

# disable swagger and redoc in production
if ENV == "production":
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None
    )
else:
    app = FastAPI(
        # send HttpOnly Cookies to Swagger UI
        swagger_ui_parameters={"withCredentials": True}
    )


# middlewares
# 1. check for staging key if in staging (this is for frontend to test the backend server, the staging key lets the frontend access the backend but other people can't access it. Render doesn't allow deployments with custom user permissions in free tier)
if ENV == "staging" and settings.STAGING_API_KEY is not None:
    from app.middleware.staging_auth import StagingAuthMiddleware

    app.add_middleware(
        StagingAuthMiddleware,
        staging_api_key=settings.STAGING_API_KEY
    )


# add this to wake up the server
@app.get("/")
@app.head("/")
async def root():
    return {"status": "awake"}


# register exception handlers to format all exceptions (pydantic, starlette, etc) to same format
register_exception_handlers(app)


# Domain Integrity Error catch in every route
@app.exception_handler(DomainIntegrityError)
async def domain_integrity_error_handler(request: Request, exc: DomainIntegrityError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": exc.error_message},
    )


app.include_router(auth_router, prefix="/api/v1")
app.include_router(skill_router, prefix="/api/v1")
app.include_router(category_router, prefix="/api/v1")


# crete a router to check db health using select 1
# @app.get("/health")
# async def check_db(session: AsyncSession = Depends(get_db_session)):
#     query = select(literal(1))
#     result = await session.execute(query)
#     return result.scalar()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI, Depends
from sqlalchemy import select, literal
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session

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
# 1. check for staging key if in staging
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


# crete a router to check db health using select 1
@app.get("/health")
async def check_db(session: AsyncSession = Depends(get_db_session)):
    query = select(literal(1))
    result = await session.execute(query)
    return result.scalar()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

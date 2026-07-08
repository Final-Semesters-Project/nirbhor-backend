from loguru import logger
from app.api.v1.router import api_router
from fastapi import FastAPI
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from contextlib import asynccontextmanager
from app.core.logging import setup_logging
from app.db.seed import seed_categories_and_skills, create_admin_user
from app.db.session import AsyncSessionLocal

app_kwargs = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs on startup, before any requests
    # runs once on startup
    setup_logging()
    async with AsyncSessionLocal() as db:
        await seed_categories_and_skills(db)
        await create_admin_user(db)

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.jobs.booking_jobs import send_booking_followup_notifications, expire_stale_bookings, send_completion_prompts, auto_complete_stale_bookings
    from app.jobs.urgent_jobs import expire_stale_broadcasts

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_booking_followup_notifications,
        "interval", minutes=5
    )
    scheduler.add_job(expire_stale_broadcasts, "interval", minutes=1)
    scheduler.add_job(send_completion_prompts, "interval", hours=1)

    scheduler.add_job(expire_stale_bookings, "cron", hour=0, minute=0)
    scheduler.add_job(
        auto_complete_stale_bookings,
        "cron", hour=1, minute=0
    )  # nightly

    scheduler.start()
    logger.success("APScheduler started successfully inside lifespan startup.")

    # initialize firebase
    from app.core.firebase import init_firebase
    init_firebase()

    # runs on shutdown, after all requests
    yield
    logger.info("Shutting down APScheduler..")
    scheduler.shutdown()


# check if in production or development
ENV = settings.APP_ENV or "development"

# disable swagger and redoc in production
if ENV == "production":
    # app = FastAPI(
    #     docs_url=None,
    #     redoc_url=None,
    #     openapi_url=None
    # )
    app_kwargs.update({
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None
    })
else:
    # app = FastAPI(
    #     # send HttpOnly Cookies to Swagger UI
    #     swagger_ui_parameters={"withCredentials": True}
    # )
    app_kwargs.update({
        "swagger_ui_parameters": {"withCredentials": True}
    })

app = FastAPI(lifespan=lifespan, **app_kwargs)

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

app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

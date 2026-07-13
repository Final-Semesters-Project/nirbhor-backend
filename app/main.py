from loguru import logger
from app.api.v1.router import api_router
from fastapi import FastAPI
from app.core.cloudinary_helpers import init_cloudinary
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from contextlib import asynccontextmanager
from app.core.logging import setup_logging
from app.db.seed import seed_categories_and_skills, create_admin_user
from app.db.session import AsyncSessionLocal

# TODO: use UptimeRobot to keep Render app alive

app_kwargs = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs on startup, before any requests, runs once on startup
    setup_logging()
    init_cloudinary()

    async with AsyncSessionLocal() as db:
        await seed_categories_and_skills(db)
        await create_admin_user(db)

    # initialize firebase before starting the scheduler
    from app.core.firebase import init_firebase
    init_firebase()

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.jobs.booking_jobs import send_booking_followup_notifications, expire_stale_bookings, send_completion_prompts, auto_complete_stale_bookings
    from app.jobs.urgent_jobs import expire_stale_broadcasts
    from app.jobs.ai_summary_job import generate_ai_review_summaries
    from app.core.cache import TokenBlockListService
    from app.jobs.cloudinary_cleanup_job import cleanup_orphan_cloudinary_images

    scheduler = AsyncIOScheduler()

    # send notifications to seekers for INITIATED bookings
    scheduler.add_job(
        send_booking_followup_notifications,
        "interval", minutes=5, max_instances=1
    )

    # set the created broadcasts to EXPIRED if they're older than 5 minutes
    scheduler.add_job(
        expire_stale_broadcasts,
        "interval", minutes=1, max_instances=1
    )

    # send Seeker notifications to ask if the booking is complete
    scheduler.add_job(
        send_completion_prompts,
        "interval", hours=1,  max_instances=1
    )

    # expires the INITIATED bookings older than 48 hours
    scheduler.add_job(
        expire_stale_bookings,
        "cron", hour=0, minute=0, max_instances=1
    )

    # set IN_PROGRESS bookings to COMPLETED if they're 72 hours past work_schedule
    scheduler.add_job(
        auto_complete_stale_bookings,
        "cron", hour=1, minute=0, max_instances=1
    )

    # clean up block-list tokens every 30 minutes. Block-listed tokens are those that have not expired yet but the user has logged out.
    scheduler.add_job(
        TokenBlockListService.cleanup,
        "interval", minutes=30
    )

    # generate AI review summaries every Sunday at 2 AM
    scheduler.add_job(
        generate_ai_review_summaries, "cron",
        day_of_week="sun", hour=2, minute=0, max_instances=1
    )

    # clean up cloudinary orphan images every Sunday at 3 AM
    scheduler.add_job(
        cleanup_orphan_cloudinary_images,
        "cron", day_of_week="sun", hour=3, minute=0, max_instances=1
    )

    # start the scheduler
    scheduler.start()
    logger.success("APScheduler started successfully.")

    yield  # run the app

    # runs on shutdown, after all requests
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

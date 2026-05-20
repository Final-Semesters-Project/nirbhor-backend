from fastapi import FastAPI
from app.core.config import settings

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


# add this to wake up the server
@app.get("/")
@app.head("/")
async def root():
    return {"status": "awake"}


# crete a router to check db health using select 1


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

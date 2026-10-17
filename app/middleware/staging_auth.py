from fastapi import Request, Response
from fastapi.responses import JSONResponse
from app.core.config import settings
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import SecretStr

# routes that don't require auth
EXCLUDED_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}

class StagingAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, staging_api_key: SecretStr):
        super().__init__(app)  # get all the properties from BaseHTTPMiddleware/parent
        self.staging_api_key = staging_api_key  # stored on instance, not class

    async def dispatch(self, request: Request, call_next) -> Response:
        # allow health check routes through without auth
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        key = request.headers.get("X-Staging-Key")

        # .get_secret_value() extracts the plain string from SecretStr
        # Without this, SecretStr("abc") != "abc" even if the value matches
        if key != self.staging_api_key.get_secret_value():
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Forbidden: Invalid or missing staging key"}
            )
        return await call_next(request)

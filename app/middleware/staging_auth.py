from fastapi import Request, Response
from fastapi.responses import JSONResponse
from app.core.config import settings
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import SecretStr


class StagingAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, staging_api_key: SecretStr):
        super().__init__(app)  # get all the properties from BaseHTTPMiddleware/parent
        self.staging_api_key = staging_api_key  # stored on instance, not class

        async def dispatch(self, request: Request, call_next) -> Response:
            # allow health check routes through without auth
            if request.url.path in ["/", "/health", "/docs", "/redoc", "/openapi.json"]:
                return await call_next(request)

            key = request.headers.get("X-Staging-Key")

            if key != self.staging_api_key:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Forbidden: Invalid or missing staging key"}
                )
            return await call_next(request)

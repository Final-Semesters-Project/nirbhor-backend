from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.i18n import t


# Domain Integrity Error: Catches Database Integrity Errors & shows a readable error message
class DomainIntegrityError(Exception):
    def __init__(self, error_message: str, raw_error: str | None = None):
        self.error_message = error_message
        self.raw_error = raw_error
        super().__init__(error_message)

    def __str__(self) -> str:
        return self.error_message


# extract error messages from pydantic validation errors(422 Unprocessable Content)
def register_exception_handlers(app):
    """Register all global exception handlers on the FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError
    ) -> JSONResponse:
        """
        Normalize Pydantic 422 errors to match our standard error format.
        Extracts the first error message for simplicity.
        """
        errors = exc.errors()

        # extract human readable messages from pydantic errors
        messages = []
        for error in errors:
            field = " → ".join(str(loc)
                               for loc in error["loc"] if loc != "body")
            msg = error["msg"]
            messages.append(f"{field}: {msg}" if field else msg)

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": messages[0] if len(messages) == 1 else messages,
                # single error → string, multiple → list
                # frontend checks: typeof detail === 'string' vs Array.isArray(detail)
            }
        )

    # normalize all HTTP exceptions
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException
    ) -> JSONResponse:
        """Normalize all HTTP exceptions to same format."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )

    @app.exception_handler(DomainIntegrityError)
    async def domain_integrity_error_handler(
        request: Request,
        exc: DomainIntegrityError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.error_message}
        )

    @app.exception_handler(Exception)
    async def global_unhandled_exception_handler(request: Request, exc: Exception):
        # 1. Log the absolute truth securely on the machine
        logger.critical(
            f"Unhandled system exception on {request.url.path}: {exc}", exc_info=True)

        # 2. Sniff out language from header for localization
        accept_lang = request.headers.get("accept-language", "en")
        lang = "bn" if accept_lang.startswith("bn") else "en"

        # 3. Send back a polished, safe, completely generic JSON payload
        return JSONResponse(
            status_code=500,
            content={"detail": t("internal_server_error", lang)}
        )

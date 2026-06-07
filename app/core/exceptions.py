from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.i18n import t


# Domain Integrity Error: Catches Database Integrity Errors & shows a readable error message
class DomainIntegrityError(Exception):
    """
    409 Conflict — resource already exists or conflicts with current state.
    Examples: duplicate phone number, duplicate booking.
    Raised in the service layer only.
    """

    def __init__(self, error_message: str, raw_error: str | None = None):
        self.error_message = error_message
        self.raw_error = raw_error
        super().__init__(error_message)

    def __str__(self) -> str:
        return self.error_message


class DomainValidationError(Exception):
    """
    400 Bad Request — client sent semantically invalid data that passed
    Pydantic schema validation but failed business/DB validation.
    Examples: non-existent skill IDs, invalid category reference.
    Raised in the service layer only.
    """

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

        logger.debug(
            f"Validation error(pydantic 422) on {request.method} {request.url.path}: {messages}"
        )

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

        if exc.status_code >= 500:
            logger.critical(
                f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}"
            )
        else:
            logger.warning(
                f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}"
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )

    @app.exception_handler(DomainIntegrityError)
    async def domain_integrity_error_handler(
        request: Request,
        exc: DomainIntegrityError
    ) -> JSONResponse:
        """
        409 Conflict for business rule violations.
        raw_error is logged server-side only — never sent to the client.
        """
        logger.error(
            f"Domain integrity error on {request.method} {request.url.path}: "
            f"message= '{exc.error_message}' raw_error= '{exc.raw_error}'"
        )

        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.error_message}
        )

    @app.exception_handler(DomainValidationError)
    async def domain_validation_error_handler(
        request: Request,
        exc: DomainValidationError
    ) -> JSONResponse:
        logger.warning(
            f"DomainValidationError on {request.method} {request.url.path}: "
            f"message='{exc.error_message}' raw='{exc.raw_error}'"
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.error_message}
        )

    @app.exception_handler(Exception)
    async def global_unhandled_exception_handler(request: Request, exc: Exception):
        """
        Catch-all for any unhandled exception.
        Logs the full traceback securely. Returns a generic message to the client.
        """

        # 1. Log the absolute truth securely on the machine
        logger.opt(exception=exc).critical(
            f"Unhandled exception on {request.method} {request.url.path}")

        # 2. Sniff out language from header for localization
        accept_lang = request.headers.get("accept-language", "en")
        lang = "bn" if accept_lang.startswith("bn") else "en"

        # 3. Send back a polished, safe, completely generic JSON payload
        return JSONResponse(
            status_code=500,
            content={"detail": t("internal_server_error", lang)}
        )

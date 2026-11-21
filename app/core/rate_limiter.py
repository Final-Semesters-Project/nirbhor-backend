from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

# get_remote_address extracts the client's IP from the request
# This is the "key" — each IP gets its own separate counter
limiter = Limiter(key_func=get_remote_address)

def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
   """
   returns my standard error format instead of slowapi's default.
   exc is typed as Exception (required by FastAPI's add_exception_handler signature)
   but at runtime it will always be RateLimitExceeded when triggered by slowapi.
   """
   return JSONResponse(
      status_code=429,
      content={"detail": "Too many requests. Please try again later."}
   )
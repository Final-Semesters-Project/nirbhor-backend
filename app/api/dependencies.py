from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
# from app.core.cache_user import CacheService
# from app.core.jwt import decode_access_token
from app.core.security import Security
from app.db.session import get_db_session
from app.models.user_model import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


async def get_current_user(
        request: Request,
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db_session)) -> User | None:
    try:
        # get the payload from token
        payload = Security.decode_access_token(token)

        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired or invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # get the uuid
        uuid = str(payload.get("sub"))

        if uuid is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        # TODO: create cache
        # get the user from cache if exists
        # cached_user = CacheService.get_user(username)
        # if cached_user:
        #     logger.success(f"User {username} found in cache")
        #     return cached_user

        # TODO: get the user from database if not in cache
        # TODO: set user in cache
        # CacheService.set_user(user.username, user)
        # logger.success(f"Setting user {user.username} in cache")
        # Return user
        pass
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )


# async def get_current_user(
#         request: Request,
#         token: str = Depends(oauth2_scheme),
#         db: AsyncSession = Depends(get_db_session)) -> User:  # type: ignore

#     # this will extract the (sub, iat, exp) from the token
#     payload = decode_access_token(token)

#     if payload is None:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired or invalid",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

#     username = str(payload.get("sub"))  # get the username from sub

#     if username is None:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token payload"
#         )

#     # get the user from cache if exists
#     cached_user = CacheService.get_user(username)
#     if cached_user:
#         logger.success(f"User {username} found in cache")
#         return cached_user

#     # get the user from database if not in cache
#     statement = select(User).where(User.username == username)
#     result = await db.execute(statement)
#     user = result.scalar_one_or_none()

#     if not user:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
#                             detail="Could not validate credentials")

#     # attach user_id to request.state
#     request.state.user_id = user.id

#     # set user in cache
#     CacheService.set_user(user.username, user)
#     logger.success(f"Setting user {user.username} in cache")

#     return use


# Integrity error parser
"""
import re


def parse_integrity_error(error_msg: str) -> str:

Parse/Extract readable message from PostgreSQL IntegrityError
example: 'Key (registration)=(213313316) already exists'
output: 'Registration 213313316 already exists'

    # constraint name checks

    # --- Student Tables Constraints ---
    if "students_registration_key" in error_msg:
        # get the value using Regex
        match = re.search(r"Key \(registration\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"Registration number '{val}' already exists in our records."

    if "students_user_id_key" in error_msg:
        return "This user is already assigned to another student profile."

    # --- User Tables Constraints ---
    if "users_username_key" in error_msg:
        match = re.search(r"Key \(username\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"The username '{val}' is already registered."

    if "users_email_key" in error_msg:
        match = re.search(r"Key \(email\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"The email address '{val}' is already registered."

    if "users_mobile_number_key" in error_msg or "mobile_number" in error_msg.lower():
        return "This mobile number is already used for another user."

    # --- Teacher Tables Constraints ---
    if "teachers_user_id_key" in error_msg:
        return "This user is already assigned to another teacher profile."

    # --- Department Tables Constraints ---
    if "departments_department_name_key" in error_msg:
        match = re.search(r"Key \(department_name\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"A department named '{val}' already exists."

    # --- Semester Tables Constraints ---
    if "semesters_semester_name_key" in error_msg:
        match = re.search(r"Key \(semester_name\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"Semester name '{val}' already exists."

    if "semesters_semester_number_key" in error_msg:
        match = re.search(r"Key \(semester_number\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"Semester number '{val}' is already assigned."

    # --- Subject Tables Constraints ---
    if "subjects_subject_code_key" in error_msg:
        match = re.search(r"Key \(subject_code\)=\((.*?)\)", error_msg)
        val = match.group(1) if match else ""
        return f"A subject with code '{val}' already exists."

    # --- Mark Tables Constraints ---
    if "unique_mark_record" in error_msg:
        return "A mark entry already exists for this student in the selected subject and semester."

    # If no constraint name found (default message)
    return "A data integrity error has occurred. Please check your input and try again."

"""

# exceptions.py
"""
class DomainIntegrityError(Exception):
    def __init__(self, error_message: str, raw_error: str | None = None):
        self.error_message = error_message
        self.raw_error = raw_error
        super().__init__(error_message)

    def __str__(self) -> str:
        return self.error_message

"""

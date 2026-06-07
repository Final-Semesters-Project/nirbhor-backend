# app/core/schema_validators.py
# Reusable validators that work WITH or WITHOUT language context
import re
from loguru import logger
from pydantic import ValidationInfo
from app.core.i18n import t


def validate_phone(phone: str, info: ValidationInfo) -> str:
    pattern = r'^01[3-9]\d{8}$'
    if not re.match(pattern, phone):
        lang = info.context.get("lang", "en") if info.context else "en"
        logger.error(f"Invalid phone number schema check: {phone}")
        raise ValueError(t("invalid_phone", lang))
    return phone


def validate_password(password: str, info: ValidationInfo) -> str:
    if len(password) < 8:
        logger.error("Password must be at least 8 characters")
        lang = info.context.get("lang", "en") if info.context else "en"
        raise ValueError(t("password_too_short", lang))
    return password


def validate_radius(radius: int, info: ValidationInfo) -> int:
    if radius < 1 or radius > 5:
        logger.error("Working radius must be between 1 and 5 km")
        lang = info.context.get("lang", "en") if info.context else "en"
        raise ValueError(t("invalid_radius", lang))
    return radius


def validate_name(name: str, info: ValidationInfo) -> str:
    if not name or not name.strip():
        logger.error("Name is required")
        lang = info.context.get("lang", "en") if info.context else "en"
        raise ValueError(t("name_required", lang))
    return name.strip()

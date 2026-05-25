from typing import Type, TypeVar

from fastapi import Depends, Request
from loguru import logger
from pydantic import BaseModel
# Translation Dictionary for messages

MESSAGES = {
    "en": {
        "registration_failed": "Registration failed. Please try again.",
        "phone_number_exists": "An account with this phone number already exists.",
        "invalid_phone_number": "Invalid Bangladeshi phone number. Must be 11 digits starting with 01.",
        "password_too_short": "Password must be at least 8 characters",
        "invalid_working_radius": "Working radius must be between 1 and 5 km",
        "skill_creation_failed": "Skill creation failed. Please try again.",
        "invalid_skill": "One or more selected skills do not exist.",
        "invalid_category": "Selected category does not exist.",
        "user_not_found": "User not found.",
        "invalid_credentials": "Invalid phone number or password.",
        "token_expired": "Session expired. Please login again.",
        "account_suspended": "Your account has been suspended.",
        "fk_violation": "Referenced record does not exist.",
        "unique_violation": "A record with this value already exists.",
        "integrity_error": "Data integrity error. Please check your input.",
        "existing_skill": "Skill already exists.",
    },
    "bn": {
        "registration_failed": "নিবন্ধন ব্যর্থ হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।",
        "phone_number_exists": "এই ফোন নম্বর দিয়ে ইতিমধ্যে একটি অ্যাকাউন্ট তৈরি করা আছে।",
        "invalid_phone": "ভুল বাংলাদেশী ফোন নম্বর। অবশ্যই ০১ দিয়ে শুরু হওয়া ১১ ডিজিটের হতে হবে।",
        "password_too_short": "পাসওয়ার্ডটি কমপক্ষে ৮ অক্ষরের হতে হবে।",
        "invalid_working_radius": "কাজের পরিধি অবশ্যই ১ থেকে ৫ কিলোমিটারের মধ্যে হতে হবে।",
        "skill_creation_failed": "দক্ষতা তৈরি করা সম্ভব হয়নি। অনুগ্রহ করে আবার চেষ্টা করুন।",

        "invalid_skill": "এক বা একাধিক দক্ষতা বিদ্যমান নেই।",
        "invalid_category": "নির্বাচিত বিভাগ বিদ্যমান নেই।",
        "user_not_found": "ব্যবহারকারী পাওয়া যায়নি।",
        "invalid_credentials": "ভুল ফোন নম্বর বা পাসওয়ার্ড।",
        "token_expired": "সেশন মেয়াদ শেষ। আবার লগইন করুন।",
        "account_suspended": "আপনার অ্যাকাউন্ট স্থগিত করা হয়েছে।",
        "fk_violation": "সংশ্লিষ্ট রেকর্ড বিদ্যমান নেই।",
        "unique_violation": "এই মানের একটি রেকর্ড ইতিমধ্যে বিদ্যমান।",
        "integrity_error": "ডেটা ত্রুটি। আপনার ইনপুট পরীক্ষা করুন।",
        "existing_skill": "এই দক্ষতা ইতিমধ্যে বিদ্যমান।",
    }
}

# =========================== Translation ===========================


def get_lang(request: Request) -> str:
    lang = request.headers.get("Accept-Language", "en")
    logger.info(f"Accept-Language: {lang}")
    return "bn" if lang.startswith("bn") else "en"


def t(key: str, lang: str) -> str:
    """Translate a message key to the given language. Falls back to English."""
    return MESSAGES.get(lang, MESSAGES["en"]).get(key, MESSAGES["en"].get(key, key))


"""
# step 1: get the language dict
# if lang="bn" → returns MESSAGES["bn"]
# if lang="xyz" (unknown) → falls back to MESSAGES["en"]
lang_dict = MESSAGES.get(lang, MESSAGES["en"])

# step 2: get the message for this key from that language dict
# if key exists in bn dict → returns Bangla message
# if key doesn't exist in bn dict → falls back to English message
#   MESSAGES["en"].get(key, key) means:
#   if key exists in English → return English message
#   if key doesn't even exist in English → return the key itself as last resort
message = lang_dict.get(key, MESSAGES["en"].get(key, key))
"""


# TODO: Use this as dependency in routers wherever the schema contains field validators => Depends(make_validated_body(YourSchema))
T = TypeVar("T", bound=BaseModel)


def make_validated_body(schema_class: Type[T]):
    """
    Factory that returns a FastAPI dependency which:
    1. Reads raw request body
    2. Validates it using the given schema
    3. Passes language context so validators can return translated errors

    Usage:
        data: SeekerRegisterSchema = Depends(make_validated_body(SeekerRegisterSchema))
    """
    async def dependency(
        request: Request,
        lang: str = Depends(get_lang),
    ) -> T:
        raw_body = await request.json()
        # model_validate with context passes lang into field_validators
        return schema_class.model_validate(raw_body, context={"lang": lang})

    return dependency

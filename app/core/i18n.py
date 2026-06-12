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
        "skill_created": "Skill created successfully.",
        "skill_not_found.": "Skill not found.",
        "category_creation_failed": "Category creation failed. Please try again.",
        "invalid_skill": "One or more selected skills do not exist.",
        "invalid_skill_ids": "One or more selected skill IDs do not exist.",
        "invalid_category": "Selected category does not exist.",
        "category_exists": "Category already exists.",
        "category_does_not_exists": "Category does not exists.",
        "user_not_found": "User not found.",
        "invalid_credentials": "Invalid login credentials.",
        "token_expired": "Session expired. Please login again.",
        "account_suspended": "Your account has been suspended.",
        "fk_violation": "Referenced record does not exist.",
        "unique_violation": "A record with this value already exists.",
        "integrity_error": "Data integrity error. Please check your input.",
        "existing_skill": "Skill already exists.",
        "booking_not_found": "Booking not found.",
        "reported_user_not_found": "Reported user not found.",
        "reporter_not_found": "Reporter not found.",
        "provider_not_found": "Provider not found.",
        "seeker_not_found": "Seeker not found.",
        "team_leader_not_found": "Team leader not found.",
        "booking_review_not_found": "Booking for review not found.",
        "reviewee_not_found": "Reviewee not found.",
        "reviewer_not_found": "Reviewer not found.",
        "bookings_provider_not_found": "The service provider for this booking could not be found.",
        "bookings_seeker_not_found": "The service seeker for this booking could not be found.",
        "bookings_skill_not_found": "The skill for this booking could not be found.",
        "bookings_team_not_found": "The team for this booking could not be found.",
        "fcm_token_user_not_found": "The user for this fcm token could not be found.",
        "duplicate_review_error": "You have already reviewed this booking.",
        "duplicate_fcm_token_error": "This device is already registered.",
        "duplicate_refresh_token_error": "This token is already used.",
        "duplicate_version_platform_key_error": "This version platform key is already used.",
        "invalid_radius": "Invalid working radius. Value must be between 1 and 5.",
        "category_created": "Category created successfully.",
        "name_required": "Name is required.",
        "login_failed": "Login failed. Check your credentials.",
        "account_suspended": "Your account has been suspended.",
        "unauthorized_access": "You are not authorized to perform this action.",
        "profile_update_failed": "Profile update failed. Please try again.",
        "profile_updated": "Profile updated successfully.",
        "location_update_limit": "7 days haven't passed after your last location update. Try again when 7 days have passed.",
        "radius_update_limit": "7 days haven't passed after your last radius update. Try again when 7 days have passed.",
        "add_skills_to_provider_failed": "Failed to add skills. Please try again.",
        "new_skill_added": "New skill added successfully.",
        "internal_server_error": "Internal server error. Please try again.",
        "nid_already_verified": "NID already verified. Can not upload again.",
        "booking_wrong_status": "This booking cannot be updated at this stage.",
        "booking_not_yours":  "You are not authorized to update this booking.",
        "too_many_open_bookings": "You can unlock up to 10 provider numbers at a time. Please wait 2 hours before unlocking more.",
        "provider_unavailable": "This provider is currently unavailable.",
        "broadcast_not_found": "Broadcast not found or already expired.",
        "broadcast_already_claimed": "Sorry, another provider has already claimed this.",
        "broadcast_created": "Urgent broadcast sent. Waiting for a provider.",
        "no_providers_found": "No providers found in your area.",
        "work_schedule_required": "work schedule is required when hired is true.",
        "work_schedule_must_be_future": "work schedule must be a future time.",
        "provider_unskilled": "This skill is not available for this provider.",
        "search_radius_expanded_warning": "Search radius expanded to find more providers.",
    },
    "bn": {
        "registration_failed": "নিবন্ধন ব্যর্থ হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।",
        "phone_number_exists": "এই ফোন নম্বর দিয়ে ইতিমধ্যে একটি অ্যাকাউন্ট তৈরি করা আছে।",
        "invalid_phone": "ভুল বাংলাদেশী ফোন নম্বর। অবশ্যই ০১ দিয়ে শুরু হওয়া ১১ ডিজিটের হতে হবে।",
        "password_too_short": "পাসওয়ার্ডটি কমপক্ষে ৮ অক্ষরের হতে হবে।",
        "invalid_working_radius": "কাজের পরিধি অবশ্যই ১ থেকে ৫ কিলোমিটারের মধ্যে হতে হবে।",
        "skill_creation_failed": "দক্ষতা তৈরি করা সম্ভব হয়নি। অনুগ্রহ করে আবার চেষ্টা করুন।",
        "skill_created": "দক্ষতা সফলভাবে তৈরি করা হয়েছে।",
        "category_creation_failed": "ক্যাটাগরি তৈরি করা সম্ভব হয়নি। অনুগ্রহ করে আবার চেষ্টা করুন।",
        "skill_not_found.": "দক্ষতা খুঁজে পাওয়া যায়নি।",
        "category_exists": "বিভাগটি ইতিমধ্যেই বিদ্যমান।",
        "category_does_not_exists": "বিভাগ পাওয়া যায়নি।",
        "invalid_skill": "এক বা একাধিক দক্ষতা বিদ্যমান নেই।",
        "invalid_skill_ids": "এক বা একাধিক দক্ষতা আইডি বিদ্যমান নেই।",
        "invalid_category": "নির্বাচিত বিভাগ বিদ্যমান নেই।",
        "user_not_found": "ব্যবহারকারী পাওয়া যায়নি।",
        "invalid_credentials": "ভুল লগইন ক্রেডেন্শিয়াল।",
        "token_expired": "সেশন মেয়াদ শেষ। আবার লগইন করুন।",
        "account_suspended": "আপনার অ্যাকাউন্ট স্থগিত করা হয়েছে।",
        "fk_violation": "সংশ্লিষ্ট রেকর্ড বিদ্যমান নেই।",
        "unique_violation": "এই মানের একটি রেকর্ড ইতিমধ্যে বিদ্যমান।",
        "integrity_error": "ডেটা ত্রুটি। আপনার ইনপুট পরীক্ষা করুন।",
        "existing_skill": "এই দক্ষতা ইতিমধ্যে বিদ্যমান।",
        "booking_not_found": "বুকিং পাওয়া যায়নি।",
        "reported_user_not_found": "রিপোর্ট করা ব্যবহারকারীকে খুঁজে পাওয়া যায়নি।",
        "reporter_not_found": "প্রতিবেদককে খুঁজে পাওয়া যায়নি।",
        "provider_not_found": "সরবরাহকারী খুঁজে পাওয়া যায়নি।",
        "seeker_not_found": "অনুসন্ধানকারী খুঁজে পাওয়া যায়নি।",
        "team_leader_not_found": "দলনেতা খুঁজে পাওয়া যায়নি।",
        "booking_review_not_found": "পর্যালোচনার জন্য বুকিং পাওয়া যায়নি।",
        "reviewee_not_found": "পর্যালোচনাকারীকে খুঁজে পাওয়া যায়নি।",
        "reviewer_not_found": "পর্যালোচককে খুঁজে পাওয়া যায়নি।",
        "bookings_provider_not_found": "এই বুকিংয়ের জন্য পরিষেবা প্রদানকারীকে খুঁজে পাওয়া যায়নি।",
        "bookings_seeker_not_found": "এই বুকিংয়ের জন্য পরিষেবা গ্রহণকারীকে খুঁজে পাওয়া যায়নি।",
        "bookings_skill_not_found": "এই বুকিংয়ের জন্য প্রয়োজনীয় দক্ষতা খুঁজে পাওয়া যায়নি।",
        "bookings_team_not_found": "এই বুকিংয়ের জন্য টিমটিকে খুঁজে পাওয়া যায়নি।",
        "fcm_token_user_not_found": "এই এফসিএম টোকেনের ব্যবহারকারীকে খুঁজে পাওয়া যায়নি।",
        "duplicate_review_error": "আপনি ইতিমধ্যে এই বুকিংয়ের রিভিউ দিয়েছেন।",
        "duplicate_fcm_token_error": "এই ডিভাইসটি ইতিমধ্যে নিবন্ধিত।",
        "duplicate_refresh_token_error": "এই টোকেনটি ইতিমধ্যে ব্যবহৃত হয়েছে।",
        "duplicate_version_platform_key_error": "এই সংস্করণের প্ল্যাটফর্ম কী ইতিমধ্যেই ব্যবহৃত হয়েছে।",
        "invalid_radius": "কাজের পরিধি সঠিক নয়। মানটি ১ থেকে ৫ এর মধ্যে হতে হবে।",
        "category_created": "ক্যাটাগরি সফলভাবে তৈরি হয়েছে।",
        "name_required": "নাম প্রয়োজনীয়।",
        "login_failed": "লগইন ব্যর্থ হয়েছে। ক্রেডেনশিয়ালস পরীক্ষা করুন।",
        "account_suspended": "আপনার অ্যাকাউন্ট স্থগিত করা হয়েছে।",
        "unauthorized_access": "আপনি এই কাজটি প্রদর্শন করার অনুমতি নেই।",
        "profile_update_failed": "প্রোফাইল আপডেট ব্যর্থ হয়েছে। পুনরায় চেষ্টা করুন।",
        "profile_updated": "প্রোফাইল সফলভাবে আপডেট হয়েছে।",
        "location_update_limit": "আপনার শেষ অবস্থান আপডেটের পর ৭ দিন অতিবাহিত হয়নি। ৭ দিন অতিবাহিত হলে আবার চেষ্টা করুন।",
        "radius_update_limit": "আপনার কাজের পরিধি আপডেটের পর ৭ দিন অতিবাহিত হয়নি। ৭ দিন অতিবাহিত হলে আবার চেষ্টা করুন।",
        "add_skills_to_provider_failed": "দক্ষতা যুক্ত করা ব্যর্থ হয়েছে। পুনরায় চেষ্টা করুন।",
        "new_skill_added": "নতুন দক্ষতা সফলভাবে যুক্ত হয়েছে।",
        "internal_server_error": "অভ্যন্তরীণ সার্ভার ত্রুটি। পুনরায় চেষ্টা করুন।",
        "empty_data": "কোন তথ্য প্রদান করা হয়নি।",
        "nid_already_verified": "এনআইডি ইতিমধ্যে যাচাই করা হয়েছে। পুনরায় আপলোড করা যাবে না।",
        "booking_wrong_status": "এই বুকিং এখন আপডেট করা যাবে না।",
        "booking_not_yours": "এই বুকিং আপডেট করার অনুমতি নেই।",
        "too_many_open_bookings": "আপনি একসাথে সর্বোচ্চ ১০টি প্রোভাইডারের নম্বর আনলক করতে পারবেন। আরও আনলক করতে ২ ঘণ্টা অপেক্ষা করুন।",
        "provider_unavailable": "এই প্রোভাইডার এখন উপলব্ধ নেই।",
        "broadcast_not_found": "ব্রডকাস্ট পাওয়া যায়নি বা মেয়াদ শেষ।",
        "broadcast_already_claimed": "দুঃখিত, অন্য একজন প্রোভাইডার আগেই এটি গ্রহণ করেছেন।",
        "broadcast_created": "জরুরি অনুরোধ পাঠানো হয়েছে। প্রোভাইডারের জন্য অপেক্ষা করুন।",
        "no_providers_found": "আপনার এলাকায় কোনো প্রোভাইডার পাওয়া যায়নি।",
        "work_schedule_required": "কাজের সময়সূচি প্রদান করুন।",
        "work_schedule_must_be_future": "কাজের সময়সূচি একটি পরবর্তী সময় হতে হবে।",
        "provider_unskilled": "এই স্কিল এই প্রোভাইডারের জন্য উপলব্ধ নয়।",
        "search_radius_expanded_warning": "আরো প্রভাইডার পাওয়ার জন্য খোজার পরিধি বাড়ানো হয়েছে।",
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

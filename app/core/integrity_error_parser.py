import re

# TODO: check pgadmin4 for more key names


def parse_integrity_error(error_msg: str, lang: str = "en") -> str:
    """Parse PostgreSQL IntegrityError into readable message."""

    from app.core.i18n import t

    # ── Unique violations ──────────────────────────────────────────
    if "users_phone_en_key" in error_msg:
        return t("phone_already_exists", lang)

    if "uq_review_booking_reviewer" in error_msg:
        return "You have already reviewed this booking." if lang == "en" \
            else "আপনি ইতিমধ্যে এই বুকিংয়ের রিভিউ দিয়েছেন।"

    if "fcm_tokens_token_key" in error_msg:
        return "This device is already registered." if lang == "en" \
            else "এই ডিভাইসটি ইতিমধ্যে নিবন্ধিত।"

    # ── FK violations ──────────────────────────────────────────────
    if "provider_skill_links_skill_id_fkey" in error_msg:
        return t("invalid_skill", lang)

    if "skills_category_id_fkey" in error_msg:
        return t("invalid_category", lang)

    if "provider_skill_links_provider_id_fkey" in error_msg:
        return "Provider profile not found." if lang == "en" \
            else "প্রদানকারীর প্রোফাইল পাওয়া যায়নি।"

    # ── Generic fallbacks ──────────────────────────────────────────
    if "ForeignKeyViolationError" in error_msg:
        return t("fk_violation", lang)

    if "UniqueViolationError" in error_msg:
        return t("unique_violation", lang)

    return t("integrity_error", lang)
